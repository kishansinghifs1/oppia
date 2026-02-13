// Copyright 2025 The Oppia Authors. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS-IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Acceptance test for:
 *   CC.1. Create a collection
 *   LO.13. View a collection
 *
 * This test covers the collection creation, editing, and publishing workflow,
 * as well as searching for and playing a collection from the community library.
 */

import {UserFactory} from '../../utilities/common/user-factory';
import testConstants from '../../utilities/common/test-constants';
import {ExplorationEditor} from '../../utilities/user/exploration-editor';
import {CollectionEditor} from '../../utilities/user/collection-editor';
import {LoggedOutUser} from '../../utilities/user/logged-out-user';

const DEFAULT_SPEC_TIMEOUT_MSECS = testConstants.DEFAULT_SPEC_TIMEOUT_MSECS;
const ROLES = testConstants.Roles;

describe('Collection Creator', function () {
  let explorationCreator: ExplorationEditor;
  let collectionCreator: CollectionEditor & ExplorationEditor;
  let loggedOutLearner: LoggedOutUser;
  let explorationId1: string;
  let explorationId2: string;
  let explorationId3: string;

  beforeAll(async function () {
    // Create a regular user to create explorations. A separate user is
    // needed because users with the collection editor role see a modal
    // when clicking the "Create" button, which conflicts with the
    // direct-navigation flow in createAndPublishAMinimalExplorationWithTitle.
    explorationCreator = await UserFactory.createNewUser(
      'explorationCreator',
      'exploration_creator@example.com'
    );

    // Create a user with the collection editor role.
    collectionCreator = await UserFactory.createNewUser(
      'collectionCreator',
      'collection_creator@example.com',
      [ROLES.COLLECTION_EDITOR]
    );

    loggedOutLearner = await UserFactory.createLoggedOutUser();

    // Create three explorations for the collection.
    explorationId1 =
      await explorationCreator.createAndPublishAMinimalExplorationWithTitle(
        'First Exploration',
        'Algebra',
        true
      );
    explorationId2 =
      await explorationCreator.createAndPublishAMinimalExplorationWithTitle(
        'Second Exploration',
        'Algebra',
        false
      );
    explorationId3 =
      await explorationCreator.createAndPublishAMinimalExplorationWithTitle(
        'Third Exploration',
        'Algebra',
        false
      );
  }, DEFAULT_SPEC_TIMEOUT_MSECS);

  it(
    'should be able to create and publish a collection with multiple' +
      ' explorations',
    async function () {
      // Create a new collection.
      await collectionCreator.createNewCollection();

      // Add explorations to the collection.
      await collectionCreator.addExistingExploration(explorationId1);
      await collectionCreator.addExistingExploration(explorationId2);
      await collectionCreator.addExistingExploration(explorationId3);

      // Shift nodes in the node graph. With 3 nodes, shift-left buttons
      // exist on nodes at positions 1 and 2 (indices 0 and 1 in the buttons
      // array). Shift-right buttons exist on nodes at positions 0 and 1.
      await collectionCreator.shiftNodeLeft(0);
      await collectionCreator.shiftNodeRight(0);

      // Delete a node from the collection.
      await collectionCreator.deleteNode(1);

      // Save the draft and publish the collection.
      await collectionCreator.saveDraft();
      await collectionCreator.closeSaveModal();
      await collectionCreator.publishCollection();
      await collectionCreator.setTitle('Test Collection');
      await collectionCreator.setObjective('This is a test collection.');
      await collectionCreator.setCategory('Algebra');
      await collectionCreator.saveChanges();
    },
    DEFAULT_SPEC_TIMEOUT_MSECS
  );

  it(
    'should be able to find and play the collection from the library',
    async function () {
      // Navigate to the community library, search for the collection,
      // and play it.
      await loggedOutLearner.navigateToCommunityLibraryPage();
      await loggedOutLearner.searchForLessonInSearchBar('Test Collection');

      // Verify the collection tile is visible and click on it.
      await loggedOutLearner.page.waitForSelector(
        '.e2e-test-collection-summary-tile',
        {visible: true}
      );
      const titleElements = await loggedOutLearner.page.$$(
        '.e2e-test-collection-summary-tile-title'
      );
      let collectionFound = false;
      for (const titleElement of titleElements) {
        const text = await loggedOutLearner.page.evaluate(
          (el: Element) => (el as HTMLElement).innerText.trim(),
          titleElement
        );
        if (text === 'Test Collection') {
          collectionFound = true;
          // Click the parent anchor/tile element.
          await titleElement.evaluate(el => {
            const tile = el.closest('a') || el.closest('mat-card') || el;
            (tile as HTMLElement).click();
          });
          await loggedOutLearner.waitForPageToFullyLoad();
          break;
        }
      }
      expect(collectionFound).toBe(true);
    },
    DEFAULT_SPEC_TIMEOUT_MSECS
  );

  afterAll(async function () {
    await UserFactory.closeAllBrowsers();
  });
});
