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

"""Unit tests for jobs.batch_jobs.blog_author_details_migration_jobs."""

from __future__ import annotations

from core.jobs import job_test_utils
from core.jobs.batch_jobs import blog_author_details_migration_jobs
from core.jobs.types import job_run_result
from core.platform import models

from typing import Final, Type

MYPY = False
if MYPY:  # pragma: no cover
    from mypy_imports import blog_models
    from mypy_imports import user_models

(blog_models, user_models) = models.Registry.import_models(
    [models.Names.BLOG, models.Names.USER]
)


class MigrateBlogAuthorDetailsJobTests(job_test_utils.JobTestBase):
    """Tests for MigrateBlogAuthorDetailsJob."""

    JOB_CLASS: Type[
        blog_author_details_migration_jobs.MigrateBlogAuthorDetailsJob
    ] = blog_author_details_migration_jobs.MigrateBlogAuthorDetailsJob

    VALID_USER_ID_1: Final = 'uid_user_one_id_12345'
    VALID_USER_ID_2: Final = 'uid_user_two_id_67890'
    PSEUDONYMIZED_ID_1: Final = 'pid_pseudo_one_12345'

    def test_empty_storage(self) -> None:
        """Test that the job produces no output when there is no data."""
        self.assert_job_output_is_empty()

    def test_no_issues_produces_no_changes(self) -> None:
        """Test that valid data produces no migration actions."""
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Test Post',
            content='<p>Content</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='test-post',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='User One',
            author_bio='Bio.',
        )
        self.put_multi([user_model, blog_post, author_detail])

        self.assert_job_output_is_empty()

    def test_orphaned_model_is_deleted(self) -> None:
        """Test that an orphaned author model (no posts, no user) is deleted."""
        orphaned_model = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Orphaned Author',
            author_bio='Old bio.',
        )
        self.put_multi([orphaned_model])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(stdout='MODELS DELETED SUCCESS: 1'),
            ]
        )

        # Verify the orphaned model was deleted from the datastore.
        self.assertIsNone(
            blog_models.BlogAuthorDetailsModel.get_by_id('orphan_mdl_01')
        )

    def test_missing_model_is_created(self) -> None:
        """Test that a fallback author model is created when posts exist
        but no author details model does.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Post Without Author Details',
            content='<p>Content</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='no-author-details',
        )
        # No BlogAuthorDetailsModel for VALID_USER_ID_1.
        self.put_multi([user_model, blog_post])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(stdout='MODELS CREATED SUCCESS: 1'),
            ]
        )

        # Verify a new author details model was created in the datastore.
        created_model = blog_models.BlogAuthorDetailsModel.get_by_author(
            self.VALID_USER_ID_1
        )
        self.assertIsNotNone(created_model)
        self.assertEqual(created_model.author_id, self.VALID_USER_ID_1)
        self.assertEqual(created_model.displayed_author_name, 'Blog Author')
        self.assertEqual(created_model.author_bio, '')

    def test_missing_model_created_for_pseudonymized_author(self) -> None:
        """Test that a fallback model is created for a pseudonymized
        author_id that has posts but no author details model.
        """
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Pseudo Post',
            content='<p>Content</p>',
            author_id=self.PSEUDONYMIZED_ID_1,
            url_fragment='pseudo-post',
        )
        self.put_multi([blog_post])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(stdout='MODELS CREATED SUCCESS: 1'),
            ]
        )

        created_model = blog_models.BlogAuthorDetailsModel.get_by_author(
            self.PSEUDONYMIZED_ID_1
        )
        self.assertIsNotNone(created_model)
        self.assertEqual(created_model.author_id, self.PSEUDONYMIZED_ID_1)

    def test_multiple_orphaned_and_missing_handled_simultaneously(
        self,
    ) -> None:
        """Test that both orphaned deletions and missing creations work
        at the same time.
        """
        # Valid: user + posts + author model — no action needed.
        valid_user = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='valid@example.com',
        )
        valid_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Valid Post',
            content='<p>Valid</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='valid-post',
        )
        valid_author = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='valid_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Valid Author',
            author_bio='Valid bio.',
        )

        # Orphaned: author model, no posts, no user.
        orphaned_model = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_01',
            author_id=self.VALID_USER_ID_2,
            displayed_author_name='Orphaned Author',
            author_bio='Orphaned bio.',
        )

        # Missing: post exists, no author model.
        missing_user = self.create_model(
            user_models.UserSettingsModel,
            id='uid_missing_user_1234',
            email='missing@example.com',
        )
        missing_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_002',
            title='Missing Author Post',
            content='<p>Missing</p>',
            author_id='uid_missing_user_1234',
            url_fragment='missing-author',
        )

        self.put_multi(
            [
                valid_user,
                valid_post,
                valid_author,
                orphaned_model,
                missing_user,
                missing_post,
            ]
        )

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(stdout='MODELS DELETED SUCCESS: 1'),
                job_run_result.JobRunResult(stdout='MODELS CREATED SUCCESS: 1'),
            ]
        )

        # Orphaned model should be gone.
        self.assertIsNone(
            blog_models.BlogAuthorDetailsModel.get_by_id('orphan_mdl_01')
        )
        # Valid model should still exist.
        self.assertIsNotNone(
            blog_models.BlogAuthorDetailsModel.get_by_id('valid_mdl_01')
        )
        # Missing model should now exist.
        created = blog_models.BlogAuthorDetailsModel.get_by_author(
            'uid_missing_user_1234'
        )
        self.assertIsNotNone(created)

    def test_author_model_with_user_but_no_posts_is_not_deleted(self) -> None:
        """Test that an author model whose author_id matches an existing
        user is NOT deleted, even if the author has no blog posts.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Author No Posts',
            author_bio='Has account but no posts.',
        )
        self.put_multi([user_model, author_detail])

        self.assert_job_output_is_empty()

        # Model should still exist.
        self.assertIsNotNone(
            blog_models.BlogAuthorDetailsModel.get_by_id('author_mdl_01')
        )

    def test_idempotency_no_double_create(self) -> None:
        """Test that running the job when an author model already exists
        for all posts does not create duplicates.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Post',
            content='<p>Content</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='post',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Author',
            author_bio='Bio.',
        )
        self.put_multi([user_model, blog_post, author_detail])

        self.assert_job_output_is_empty()

    def test_multiple_orphaned_models_same_author_all_deleted(self) -> None:
        """Test that multiple orphaned author models for the same author_id
        are all deleted.
        """
        orphan_1 = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Orphan 1',
            author_bio='Bio 1.',
        )
        orphan_2 = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_02',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Orphan 2',
            author_bio='Bio 2.',
        )
        self.put_multi([orphan_1, orphan_2])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(stdout='MODELS DELETED SUCCESS: 2'),
            ]
        )

        self.assertIsNone(
            blog_models.BlogAuthorDetailsModel.get_by_id('orphan_mdl_01')
        )
        self.assertIsNone(
            blog_models.BlogAuthorDetailsModel.get_by_id('orphan_mdl_02')
        )


class AuditMigrateBlogAuthorDetailsJobTests(job_test_utils.JobTestBase):
    """Tests for the dry-run audit version of the migration job."""

    JOB_CLASS: Type[
        blog_author_details_migration_jobs.AuditMigrateBlogAuthorDetailsJob
    ] = blog_author_details_migration_jobs.AuditMigrateBlogAuthorDetailsJob

    VALID_USER_ID_1: Final = 'uid_user_one_id_12345'

    def test_audit_does_not_delete_orphaned_model(self) -> None:
        """Test that the audit job reports deletions but does not actually
        delete the model.
        """
        orphaned_model = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Orphaned Author',
            author_bio='Old bio.',
        )
        self.put_multi([orphaned_model])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(stdout='MODELS DELETED SUCCESS: 1'),
            ]
        )

        # Model should still exist because this is a dry run.
        self.assertIsNotNone(
            blog_models.BlogAuthorDetailsModel.get_by_id('orphan_mdl_01')
        )

    def test_audit_does_not_create_missing_model(self) -> None:
        """Test that the audit job reports creations but does not actually
        create a model.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Post Without Author Details',
            content='<p>Content</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='no-author-details',
        )
        self.put_multi([user_model, blog_post])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(stdout='MODELS CREATED SUCCESS: 1'),
            ]
        )

        # Model should NOT exist because this is a dry run.
        self.assertIsNone(
            blog_models.BlogAuthorDetailsModel.get_by_author(
                self.VALID_USER_ID_1
            )
        )
