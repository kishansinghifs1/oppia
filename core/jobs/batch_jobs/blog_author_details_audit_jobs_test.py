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

"""Unit tests for jobs.batch_jobs.blog_author_details_audit_jobs."""

from __future__ import annotations

from core.jobs import job_test_utils
from core.jobs.batch_jobs import blog_author_details_audit_jobs
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


class AuditBlogAuthorDetailsJobTests(job_test_utils.JobTestBase):
    """Tests for AuditBlogAuthorDetailsJob."""

    JOB_CLASS: Type[
        blog_author_details_audit_jobs.AuditBlogAuthorDetailsJob
    ] = blog_author_details_audit_jobs.AuditBlogAuthorDetailsJob

    VALID_USER_ID_1: Final = 'uid_user_one_id_12345'
    VALID_USER_ID_2: Final = 'uid_user_two_id_67890'
    PSEUDONYMIZED_ID_1: Final = 'pid_pseudo_one_12345'
    PSEUDONYMIZED_ID_2: Final = 'pid_pseudo_two_67890'

    def test_empty_storage(self) -> None:
        """Test that the job produces no output when there is no data."""
        self.assert_job_output_is_empty()

    def test_valid_state_with_matching_posts_and_author_models(self) -> None:
        """Test that valid author models are correctly identified when blog
        posts exist and the user exists.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Test Blog Post',
            content='<p>Content</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='test-blog-post',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='User One',
            author_bio='A blog author.',
        )
        self.put_multi([user_model, blog_post, author_detail])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='VALID: model_id=author_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_1
                ),
                job_run_result.JobRunResult(stdout='TOTAL_BLOG_POSTS: 1'),
                job_run_result.JobRunResult(stdout='TOTAL_AUTHOR_MODELS: 1'),
            ]
        )

    def test_orphaned_model_detected(self) -> None:
        """Test that an author model whose author_id does not match any blog
        post or user is classified as orphaned.
        """
        orphaned_author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Old Author',
            author_bio='Old bio.',
        )
        self.put_multi([orphaned_author_detail])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stderr='ORPHANED: model_id=orphan_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_1
                ),
                job_run_result.JobRunResult(stdout='TOTAL_AUTHOR_MODELS: 1'),
            ]
        )

    def test_missing_model_detected(self) -> None:
        """Test that blog posts without a corresponding author details model
        are classified as missing.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Test Blog Post',
            content='<p>Content</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='test-blog-post',
        )
        self.put_multi([user_model, blog_post])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stderr='MISSING: author_id=%s, '
                    'sample_post_id=blog_post_001' % self.VALID_USER_ID_1
                ),
                job_run_result.JobRunResult(stdout='TOTAL_BLOG_POSTS: 1'),
            ]
        )

    def test_deleted_user_posts_counted(self) -> None:
        """Test that blog posts with pseudonymized author IDs are classified
        as deleted-user posts. When no author model exists, it is also
        classified as missing.
        """
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Pseudonymized Post',
            content='<p>Content</p>',
            author_id=self.PSEUDONYMIZED_ID_1,
            url_fragment='pseudo-post',
        )
        self.put_multi([blog_post])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='DELETED_USER_POSTS: %s' % self.PSEUDONYMIZED_ID_1
                ),
                job_run_result.JobRunResult(
                    stderr='MISSING: author_id=%s, '
                    'sample_post_id=blog_post_001' % self.PSEUDONYMIZED_ID_1
                ),
                job_run_result.JobRunResult(stdout='TOTAL_BLOG_POSTS: 1'),
            ]
        )

    def test_deleted_user_posts_with_author_model(self) -> None:
        """Test that pseudonymized posts with an existing author model are
        counted as both deleted-user posts and valid models.
        """
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Pseudonymized Post',
            content='<p>Content</p>',
            author_id=self.PSEUDONYMIZED_ID_1,
            url_fragment='pseudo-post',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.PSEUDONYMIZED_ID_1,
            displayed_author_name='Anonymous Author',
            author_bio='',
        )
        self.put_multi([blog_post, author_detail])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='DELETED_USER_POSTS: %s' % self.PSEUDONYMIZED_ID_1
                ),
                job_run_result.JobRunResult(
                    stdout='VALID: model_id=author_mdl_01, '
                    'author_id=%s' % self.PSEUDONYMIZED_ID_1
                ),
                job_run_result.JobRunResult(stdout='TOTAL_BLOG_POSTS: 1'),
                job_run_result.JobRunResult(stdout='TOTAL_AUTHOR_MODELS: 1'),
            ]
        )

    def test_multiple_issues_simultaneously(self) -> None:
        """Test that the job correctly categorizes multiple issues at once:
        a valid model, an orphaned model, a missing model, and deleted-user
        posts.
        """
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
        valid_author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='valid_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Valid Author',
            author_bio='Valid bio.',
        )

        orphaned_author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_01',
            author_id=self.VALID_USER_ID_2,
            displayed_author_name='Orphaned Author',
            author_bio='Orphaned bio.',
        )

        # Missing: post exists but no author model for this author_id.
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

        # Deleted user: pseudonymized post, no author model.
        pseudo_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_003',
            title='Pseudo Post',
            content='<p>Pseudo</p>',
            author_id=self.PSEUDONYMIZED_ID_1,
            url_fragment='pseudo-post',
        )

        self.put_multi(
            [
                valid_user,
                valid_post,
                valid_author_detail,
                orphaned_author_detail,
                missing_user,
                missing_post,
                pseudo_post,
            ]
        )

        self.assert_job_output_is(
            [
                # Valid model.
                job_run_result.JobRunResult(
                    stdout='VALID: model_id=valid_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_1
                ),
                # Orphaned model.
                job_run_result.JobRunResult(
                    stderr='ORPHANED: model_id=orphan_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_2
                ),
                # Missing model.
                job_run_result.JobRunResult(
                    stderr='MISSING: author_id=uid_missing_user_1234, '
                    'sample_post_id=blog_post_002'
                ),
                # Deleted user posts.
                job_run_result.JobRunResult(
                    stdout='DELETED_USER_POSTS: %s' % self.PSEUDONYMIZED_ID_1
                ),
                # Missing model for pseudonymized author.
                job_run_result.JobRunResult(
                    stderr='MISSING: author_id=%s, '
                    'sample_post_id=blog_post_003' % self.PSEUDONYMIZED_ID_1
                ),
                # Total counts.
                job_run_result.JobRunResult(stdout='TOTAL_BLOG_POSTS: 3'),
                job_run_result.JobRunResult(stdout='TOTAL_AUTHOR_MODELS: 2'),
            ]
        )

    def test_author_model_with_user_but_no_posts_is_valid(self) -> None:
        """Test that an author model whose author_id matches a user is valid,
        even if no blog posts reference that author_id (the user exists, so
        the author model is not orphaned).
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

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='VALID: model_id=author_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_1
                ),
                job_run_result.JobRunResult(stdout='TOTAL_AUTHOR_MODELS: 1'),
            ]
        )

    def test_multiple_posts_by_same_author_with_model(self) -> None:
        """Test that multiple blog posts by the same author with a
        corresponding author model are all valid.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        post_1 = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='First Post',
            content='<p>First</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='first-post',
        )
        post_2 = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_002',
            title='Second Post',
            content='<p>Second</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='second-post',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Author One',
            author_bio='Prolific writer.',
        )
        self.put_multi([user_model, post_1, post_2, author_detail])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='VALID: model_id=author_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_1
                ),
                job_run_result.JobRunResult(stdout='TOTAL_BLOG_POSTS: 2'),
                job_run_result.JobRunResult(stdout='TOTAL_AUTHOR_MODELS: 1'),
            ]
        )

    def test_is_pseudonymized_helper(self) -> None:
        """Test the _is_pseudonymized helper function."""
        self.assertTrue(
            blog_author_details_audit_jobs._is_pseudonymized('pid_abc123')
        )
        self.assertFalse(
            blog_author_details_audit_jobs._is_pseudonymized('uid_abc123')
        )
        self.assertFalse(
            blog_author_details_audit_jobs._is_pseudonymized('regular_user')
        )
