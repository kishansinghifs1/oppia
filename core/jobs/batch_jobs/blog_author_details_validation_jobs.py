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

"""Validation job to confirm BlogAuthorDetailsModel migration was successful.

This job checks that:
1. No orphaned BlogAuthorDetailsModel records remain (author model exists but
   no blog posts or user reference the author_id).
2. All blog posts have a corresponding BlogAuthorDetailsModel whose author_id
   matches the post's author_id.

The job reports PASS when all checks succeed and FAIL with details when any
issues remain.
"""

from __future__ import annotations

from core.jobs import base_jobs
from core.jobs.io import ndb_io
from core.jobs.types import job_run_result
from core.platform import models

import apache_beam as beam

from typing import Dict, List, Tuple

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import blog_models
    from mypy_imports import user_models

(blog_models, user_models) = models.Registry.import_models(
    [models.Names.BLOG, models.Names.USER]
)


class ValidateBlogAuthorDetailsJob(base_jobs.JobBase):
    """Post-migration validation job that confirms no orphaned or missing
    BlogAuthorDetailsModel records remain.
    """

    @staticmethod
    def _find_remaining_issues(
        element: Tuple[str, Dict[str, List[blog_models.BlogPostModel]]],
    ) -> List[job_run_result.JobRunResult]:
        """Checks a CoGroupByKey result for remaining issues.

        Args:
            element: tuple(str, dict). A key-value pair where the key is
                author_id and the value is a dict with keys 'posts', 'models',
                and 'users' mapping to sequences of the respective model
                instances.

        Returns:
            list(JobRunResult). A list of error results if issues are found,
            or an empty list if this group is valid.
        """
        author_id, grouped = element
        posts = list(grouped['posts'])
        author_models_list = list(grouped['models'])
        users = list(grouped['users'])

        has_posts = len(posts) > 0
        has_author_model = len(author_models_list) > 0
        has_user = len(users) > 0

        issues = []

        # Check for orphaned models: author model exists but no posts or user.
        if has_author_model and not has_posts and not has_user:
            for model in author_models_list:
                issues.append(
                    job_run_result.JobRunResult.as_stderr(
                        'ORPHANED: model_id=%s, author_id=%s'
                        % (model.id, author_id)
                    )
                )

        # Check for missing models: posts exist but no author details model.
        if has_posts and not has_author_model:
            sample_post_id = posts[0].id
            issues.append(
                job_run_result.JobRunResult.as_stderr(
                    'MISSING: author_id=%s, sample_post_id=%s'
                    % (author_id, sample_post_id)
                )
            )

        return issues

    def run(self) -> beam.PCollection[job_run_result.JobRunResult]:
        """Runs the validation pipeline.

        Returns:
            PCollection. A collection of JobRunResult. If no issues remain,
            a single PASS result is emitted. Otherwise, FAIL results are
            emitted with details of remaining issues.
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

        joined = {
            'posts': keyed_posts,
            'models': keyed_author_models,
            'users': keyed_users,
        } | 'CoGroup by author_id' >> beam.CoGroupByKey()

        issue_results = joined | 'Find remaining issues' >> beam.FlatMap(
            self._find_remaining_issues
        )

        # Count remaining issues. If zero, emit PASS; otherwise emit FAIL
        # along with the individual issue results.
        issue_count = (
            issue_results
            | 'Count remaining issues' >> beam.combiners.Count.Globally()
        )

        status_report = issue_count | 'Generate status report' >> beam.Map(
            lambda count: (
                job_run_result.JobRunResult.as_stdout(
                    'VALIDATION PASSED: No remaining issues found.'
                )
                if count == 0
                else job_run_result.JobRunResult.as_stderr(
                    'VALIDATION FAILED: %d issue(s) remaining.' % count
                )
            )
        )

        return (
            status_report,
            issue_results,
        ) | 'Combine validation results' >> beam.Flatten()
