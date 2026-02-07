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

"""Migration job to fix orphaned and missing BlogAuthorDetailsModel records.

This job performs two kinds of fixes:
1. Orphaned models: BlogAuthorDetailsModel records whose author_id does not
   match any BlogPostModel.author_id and no corresponding UserSettingsModel
   exists. These are deleted since they reference stale user IDs and serve
   no purpose.
2. Missing models: Blog posts whose author_id has no corresponding
   BlogAuthorDetailsModel. A new BlogAuthorDetailsModel is created with
   fallback data.

This job should only be run after the AuditBlogAuthorDetailsJob has been
reviewed and the results accepted by an engineer.
"""

from __future__ import annotations

from core.jobs import base_jobs
from core.jobs.io import ndb_io
from core.jobs.transforms import job_result_transforms
from core.jobs.types import job_run_result
from core.platform import models

import apache_beam as beam
import result as result_lib

from typing import Dict, Iterator, List, Tuple, Union

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import blog_models
    from mypy_imports import datastore_services
    from mypy_imports import user_models

(blog_models, user_models) = models.Registry.import_models(
    [models.Names.BLOG, models.Names.USER]
)

datastore_services = models.Registry.import_datastore_services()

# The default display name used for fallback author models created when no
# author details exist for a blog post's author_id.
_FALLBACK_DISPLAYED_AUTHOR_NAME = 'Blog Author'
# The default bio for fallback author models.
_FALLBACK_AUTHOR_BIO = ''


def _is_pseudonymized(author_id: str) -> bool:
    """Checks whether the given author ID is a pseudonymized ID.

    Args:
        author_id: str. The author ID to check.

    Returns:
        bool. Whether the author ID starts with the pseudonymized prefix.
    """
    return author_id.startswith('pid_')


class MigrateBlogAuthorDetailsJob(base_jobs.JobBase):
    """Migration job that fixes orphaned and missing BlogAuthorDetailsModel
    records. Orphaned models (no posts, no user) are deleted, and missing
    models (posts exist but no author details) get new fallback models
    created.
    """

    DATASTORE_UPDATES_ALLOWED = True

    @staticmethod
    def _process_author_group(
        element: Tuple[str, Dict[str, List[blog_models.BlogPostModel]]],
    ) -> Iterator[
        Tuple[
            str,
            Union[blog_models.BlogAuthorDetailsModel, datastore_services.Key],
        ]
    ]:
        """Processes a CoGroupByKey result and yields tagged actions.

        For each author_id, determines what migration action to take:
        - DELETE: author model exists but no posts and no user reference it.
        - CREATE: posts exist but no corresponding author details model.

        Args:
            element: tuple(str, dict). A key-value pair where the key is
                author_id and the value is a dict with keys 'posts', 'models',
                and 'users' mapping to sequences of the respective model
                instances.

        Yields:
            tuple(str, Model|Key). A tagged tuple where the first element is
            the action ('delete' or 'create') and the second element is the
            NDB key (for deletes) or a new model instance (for creates).
        """
        author_id, grouped = element
        posts = list(grouped['posts'])
        author_models_list = list(grouped['models'])
        users = list(grouped['users'])

        has_posts = len(posts) > 0
        has_author_model = len(author_models_list) > 0
        has_user = len(users) > 0

        # Orphaned: author model exists but nothing references it.
        # Delete the stale model.
        if has_author_model and not has_posts and not has_user:
            for model in author_models_list:
                yield ('delete', model.key)

        # Missing: posts exist but no author details model exists for this
        # author_id. Create a fallback model.
        if has_posts and not has_author_model:
            yield ('create', author_id)

    @staticmethod
    def _create_fallback_author_model(
        author_id: str,
    ) -> result_lib.Result[blog_models.BlogAuthorDetailsModel, Exception]:
        """Creates a new BlogAuthorDetailsModel with fallback data.

        Args:
            author_id: str. The author_id to create the model for.

        Returns:
            Result. Ok with the new model on success, Err with the
            exception on failure.
        """
        try:
            with datastore_services.get_ndb_context():
                model = blog_models.BlogAuthorDetailsModel(
                    id=blog_models.BlogAuthorDetailsModel.generate_new_instance_id(),
                    author_id=author_id,
                    displayed_author_name=_FALLBACK_DISPLAYED_AUTHOR_NAME,
                    author_bio=_FALLBACK_AUTHOR_BIO,
                )
                model.update_timestamps()
                return result_lib.Ok(model)
        except Exception as e:
            return result_lib.Err(e)

    def run(self) -> beam.PCollection[job_run_result.JobRunResult]:
        """Runs the migration pipeline.

        Returns:
            PCollection. A collection of JobRunResult reporting the migration
            actions taken (models deleted, models created, errors).
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

        # Process each group to determine migration actions.
        tagged_actions = joined | 'Process each author group' >> beam.FlatMap(
            self._process_author_group
        )

        # --- Handle DELETES (orphaned models) ---
        keys_to_delete = (
            tagged_actions
            | 'Filter delete actions'
            >> beam.Filter(lambda action: action[0] == 'delete')
            | 'Extract keys for deletion' >> beam.Map(lambda action: action[1])
        )

        delete_count_report = keys_to_delete | 'Count deleted models' >> (
            job_result_transforms.CountObjectsToJobRunResult('MODELS DELETED')
        )

        if self.DATASTORE_UPDATES_ALLOWED:
            unused_delete_result = (
                keys_to_delete
                | 'Delete orphaned models' >> ndb_io.DeleteModels()
            )

        # --- Handle CREATES (missing models) ---
        author_ids_to_create = (
            tagged_actions
            | 'Filter create actions'
            >> beam.Filter(lambda action: action[0] == 'create')
            | 'Extract author_ids for creation'
            >> beam.Map(lambda action: action[1])
        )

        create_results = (
            author_ids_to_create
            | 'Create fallback author models'
            >> beam.Map(self._create_fallback_author_model)
        )

        create_report = (
            create_results
            | 'Transform create results to job run results'
            >> (job_result_transforms.ResultsToJobRunResults('MODELS CREATED'))
        )

        if self.DATASTORE_UPDATES_ALLOWED:
            unused_put_result = (
                create_results
                | 'Filter successful creates'
                >> beam.Filter(lambda r: r.is_ok())
                | 'Unwrap created models' >> beam.Map(lambda r: r.unwrap())
                | 'Put new models into datastore' >> ndb_io.PutModels()
            )

        return (
            delete_count_report,
            create_report,
        ) | 'Combine all migration results' >> beam.Flatten()


class AuditMigrateBlogAuthorDetailsJob(MigrateBlogAuthorDetailsJob):
    """Dry-run audit version of MigrateBlogAuthorDetailsJob.

    This job inherits the full migration pipeline but skips all datastore
    writes and deletes, allowing engineers to preview what changes would
    be made.
    """

    DATASTORE_UPDATES_ALLOWED = False
