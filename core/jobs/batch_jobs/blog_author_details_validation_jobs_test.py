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

"""Unit tests for jobs.batch_jobs.blog_author_details_validation_jobs."""

from __future__ import annotations

from core.jobs import job_test_utils
from core.jobs.batch_jobs import blog_author_details_validation_jobs
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


class ValidateBlogAuthorDetailsJobTests(job_test_utils.JobTestBase):
    """Tests for ValidateBlogAuthorDetailsJob."""

    JOB_CLASS: Type[
        blog_author_details_validation_jobs.ValidateBlogAuthorDetailsJob
    ] = blog_author_details_validation_jobs.ValidateBlogAuthorDetailsJob

    VALID_USER_ID_1: Final = 'uid_user_one_id_12345'
    VALID_USER_ID_2: Final = 'uid_user_two_id_67890'
    PSEUDONYMIZED_ID_1: Final = 'pid_pseudo_one_12345'

    def test_empty_storage_passes_validation(self) -> None:
        """Test that an empty datastore passes validation."""
        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='VALIDATION PASSED: No remaining issues found.'
                ),
            ]
        )

    def test_all_valid_passes_validation(self) -> None:
        """Test that a fully valid state passes validation."""
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Valid Post',
            content='<p>Valid</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='valid-post',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Author',
            author_bio='Bio.',
        )
        self.put_multi([user_model, blog_post, author_detail])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='VALIDATION PASSED: No remaining issues found.'
                ),
            ]
        )

    def test_pseudonymized_posts_with_author_model_passes(self) -> None:
        """Test that pseudonymized posts with a matching author model
        pass validation.
        """
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Pseudo Post',
            content='<p>Pseudo</p>',
            author_id=self.PSEUDONYMIZED_ID_1,
            url_fragment='pseudo-post',
        )
        author_detail = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='author_mdl_01',
            author_id=self.PSEUDONYMIZED_ID_1,
            displayed_author_name='Anonymous',
            author_bio='',
        )
        self.put_multi([blog_post, author_detail])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='VALIDATION PASSED: No remaining issues found.'
                ),
            ]
        )

    def test_orphaned_model_fails_validation(self) -> None:
        """Test that a remaining orphaned model causes validation to fail."""
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
                job_run_result.JobRunResult(
                    stderr='VALIDATION FAILED: 1 issue(s) remaining.'
                ),
                job_run_result.JobRunResult(
                    stderr='ORPHANED: model_id=orphan_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_1
                ),
            ]
        )

    def test_missing_model_fails_validation(self) -> None:
        """Test that a missing author model for a blog post causes
        validation to fail.
        """
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_1,
            email='user1@example.com',
        )
        blog_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Post Without Author',
            content='<p>No author</p>',
            author_id=self.VALID_USER_ID_1,
            url_fragment='no-author',
        )
        self.put_multi([user_model, blog_post])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stderr='VALIDATION FAILED: 1 issue(s) remaining.'
                ),
                job_run_result.JobRunResult(
                    stderr='MISSING: author_id=%s, '
                    'sample_post_id=blog_post_001' % self.VALID_USER_ID_1
                ),
            ]
        )

    def test_multiple_issues_fail_validation(self) -> None:
        """Test that multiple remaining issues are reported and cause
        validation to fail.
        """
        # Orphaned model.
        orphaned_model = self.create_model(
            blog_models.BlogAuthorDetailsModel,
            id='orphan_mdl_01',
            author_id=self.VALID_USER_ID_1,
            displayed_author_name='Orphaned',
            author_bio='',
        )
        # Missing model: post exists without author details.
        user_model = self.create_model(
            user_models.UserSettingsModel,
            id=self.VALID_USER_ID_2,
            email='user2@example.com',
        )
        missing_post = self.create_model(
            blog_models.BlogPostModel,
            id='blog_post_001',
            title='Missing Author Post',
            content='<p>Missing</p>',
            author_id=self.VALID_USER_ID_2,
            url_fragment='missing-author',
        )
        self.put_multi([orphaned_model, user_model, missing_post])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stderr='VALIDATION FAILED: 2 issue(s) remaining.'
                ),
                job_run_result.JobRunResult(
                    stderr='ORPHANED: model_id=orphan_mdl_01, '
                    'author_id=%s' % self.VALID_USER_ID_1
                ),
                job_run_result.JobRunResult(
                    stderr='MISSING: author_id=%s, '
                    'sample_post_id=blog_post_001' % self.VALID_USER_ID_2
                ),
            ]
        )

    def test_author_model_with_user_but_no_posts_passes(self) -> None:
        """Test that an author model with a valid user but no posts passes
        validation (it is not orphaned).
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
            author_bio='Has account.',
        )
        self.put_multi([user_model, author_detail])

        self.assert_job_output_is(
            [
                job_run_result.JobRunResult(
                    stdout='VALIDATION PASSED: No remaining issues found.'
                ),
            ]
        )
