# coding: utf-8
#
# Copyright 2026 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Audit job to detect orphaned and missing BlogAuthorDetailsModel records.

This is a read-only job that identifies:
1. Orphaned models: BlogAuthorDetailsModel records whose author_id does not
   match any BlogPostModel.author_id and no corresponding UserSettingsModel
   exists.
2. Missing models: Blog posts whose author_id has no corresponding
   BlogAuthorDetailsModel.
3. Deleted user posts: Blog posts with pseudonymized (pid_*) author IDs.
4. Valid models: BlogAuthorDetailsModel records in a correct state.
"""

from __future__ import annotations

from core.jobs import base_jobs
from core.jobs.io import ndb_io
from core.jobs.types import job_run_result
from core.platform import models

import apache_beam as beam

from typing import Dict, Iterator, List, Tuple

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import blog_models
    from mypy_imports import user_models

(blog_models, user_models) = models.Registry.import_models(
    [models.Names.BLOG, models.Names.USER]
)

# Maximum number of sample IDs to include in the report for each category.
_MAX_SAMPLE_IDS = 10


def _is_pseudonymized(author_id: str) -> bool:
    """Checks whether the given author ID is a pseudonymized ID.

    Args:
        author_id: str. The author ID to check.

    Returns:
        bool. Whether the author ID starts with the pseudonymized prefix.
    """
    return author_id.startswith('pid_')


class AuditBlogAuthorDetailsJob(base_jobs.JobBase):
    """Read-only audit job that detects orphaned, missing, and deleted-user
    BlogAuthorDetailsModel records and reports counts with sample IDs.
    """

    @staticmethod
    def _categorize_author_data(
        element: Tuple[str, Dict[str, List[blog_models.BlogPostModel]]],
    ) -> Iterator[job_run_result.JobRunResult]:
        """Categorizes a CoGroupByKey result into audit categories.

        For each author_id key, determines:
        - ORPHANED: author model exists, but no blog posts use this author_id
          AND no UserSettingsModel exists for this author_id.
        - MISSING: blog posts exist for this author_id, but no author model.
        - DELETED_USER_POSTS: blog posts exist with a pseudonymized author_id.
        - VALID: author model exists AND at least one blog post uses this
          author_id (or the user still exists).

        Args:
            element: tuple(str, dict). A key-value pair where the key is
                author_id and the value is a dict with keys 'posts', 'models',
                and 'users' mapping to sequences of the respective model
                instances.

        Yields:
            JobRunResult. A categorized result for reporting.
        """
        author_id, grouped = element
        posts = list(grouped['posts'])
        author_models = list(grouped['models'])
        users = list(grouped['users'])

        has_posts = len(posts) > 0
        has_author_model = len(author_models) > 0
        has_user = len(users) > 0
        is_pseudo = _is_pseudonymized(author_id)

        # Track pseudonymized author posts (informational).
        if is_pseudo and has_posts:
            yield job_run_result.JobRunResult.as_stdout(
                'DELETED_USER_POSTS: %s' % author_id
            )

        # Orphaned: author model exists but no posts reference this author_id
        # and no user exists for it.
        if has_author_model and not has_posts and not has_user:
            for model in author_models:
                yield job_run_result.JobRunResult.as_stderr(
                    'ORPHANED: model_id=%s, author_id=%s'
                    % (model.id, author_id)
                )

        # Missing: posts exist but no author details model.
        if has_posts and not has_author_model:
            # Report once per author_id with a sample post ID.
            sample_post_id = posts[0].id
            yield job_run_result.JobRunResult.as_stderr(
                'MISSING: author_id=%s, sample_post_id=%s'
                % (author_id, sample_post_id)
            )

        # Valid: author model exists and either posts reference this author_id
        # or the user still exists.
        if has_author_model and (has_posts or has_user):
            for model in author_models:
                yield job_run_result.JobRunResult.as_stdout(
                    'VALID: model_id=%s, author_id=%s' % (model.id, author_id)
                )

    def run(self) -> beam.PCollection[job_run_result.JobRunResult]:
        """Runs the audit pipeline.

        Returns:
            PCollection. A collection of JobRunResult reporting the audit
            findings including counts and sample IDs for each category.
        """

        blog_posts = self.pipeline | 'Get all blog posts' >> ndb_io.GetModels(
            blog_models.BlogPostModel.get_all()
        )

        author_detail_models = (
            self.pipeline
            | 'Get all author detail models'
            >> ndb_io.GetModels(blog_models.BlogAuthorDetailsModel.get_all())
        )

        user_settings_models = (
            self.pipeline
            | 'Get all user settings models'
            >> ndb_io.GetModels(user_models.UserSettingsModel.get_all())
        )

        # Key each collection by author_id for CoGroupByKey.
        keyed_posts = blog_posts | 'Key posts by author_id' >> beam.Map(
            lambda post: (post.author_id, post)
        )

        keyed_author_models = (
            author_detail_models
            | 'Key author models by author_id'
            >> beam.Map(lambda model: (model.author_id, model))
        )

        keyed_users = user_settings_models | 'Key users by id' >> beam.Map(
            lambda user: (user.id, user)
        )

        # CoGroupByKey joins all three collections on author_id.
        joined = {
            'posts': keyed_posts,
            'models': keyed_author_models,
            'users': keyed_users,
        } | 'CoGroup by author_id' >> beam.CoGroupByKey()

        categorized_results = (
            joined
            | 'Categorize each author group'
            >> beam.FlatMap(self._categorize_author_data)
        )

        # Count blog posts for reporting.
        total_posts_report = (
            blog_posts
            | 'Count total blog posts' >> beam.combiners.Count.Globally()
            | 'Filter zero posts' >> beam.Filter(lambda count: count > 0)
            | 'Format total posts count'
            >> beam.Map(
                lambda count: job_run_result.JobRunResult.as_stdout(
                    'TOTAL_BLOG_POSTS: %d' % count
                )
            )
        )

        total_models_report = (
            author_detail_models
            | 'Count total author models' >> beam.combiners.Count.Globally()
            | 'Filter zero models' >> beam.Filter(lambda count: count > 0)
            | 'Format total models count'
            >> beam.Map(
                lambda count: job_run_result.JobRunResult.as_stdout(
                    'TOTAL_AUTHOR_MODELS: %d' % count
                )
            )
        )

        return (
            categorized_results,
            total_posts_report,
            total_models_report,
        ) | 'Combine all results' >> beam.Flatten()
