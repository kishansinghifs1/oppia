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
 * @fileoverview Utility class for Collection Editor page interactions
 * in Puppeteer acceptance tests.
 */

import {BaseUser} from '../common/puppeteer-utils';
import testConstants from '../common/test-constants';
import {showMessage} from '../common/show-message';

const creatorDashboardUrl = testConstants.URLs.CreatorDashboard;
const communityLibraryUrl = testConstants.URLs.CommunityLibrary;

// Creator Dashboard selectors.
const createActivityButtonSelector = '.e2e-test-create-activity';
const createCollectionButtonSelector = '.e2e-test-create-collection';

// Collection Editor selectors.
const addExplorationInputSelector = '.e2e-test-add-exploration-input';
const addExplorationButtonSelector = '.e2e-test-add-exploration-button';
const collectionEditorCardsContainerSelector =
  '.e2e-test-collection-editor-cards-container';

// Collection node editor selectors.
const editorShiftLeftSelector = '.e2e-test-editor-shift-left';
const editorShiftRightSelector = '.e2e-test-editor-shift-right';
const editorDeleteNodeSelector = '.e2e-test-editor-delete-node';

// Collection editor navbar selectors.
const saveDraftButtonSelector = '.e2e-test-save-draft-button';
const editorPublishButtonSelector = '.e2e-test-editor-publish-button';
const saveInProgressLabelSelector = '.e2e-test-save-in-progress-label';

// Save modal selectors.
const saveModalSelector = '.e2e-test-save-modal';
const commitMessageInputSelector = '.e2e-test-commit-message-input';
const closeSaveModalButtonSelector = '.e2e-test-close-save-modal-button';

// Pre-publish modal selectors.
const collectionTitleInputSelector = '.e2e-test-collection-editor-title-input';
const collectionObjectiveInputSelector =
  '.e2e-test-collection-editor-objective-input';
const collectionCategoryDropdownSelector =
  '.e2e-test-collection-editor-category-dropdown';
const collectionSaveChangesButtonSelector =
  '.e2e-test-collection-save-changes-button';

// Community Library selectors.
const searchInputSelector = '.e2e-test-search-input';
const collectionSummaryTileSelector = '.e2e-test-collection-summary-tile';
const collectionSummaryTileTitleSelector =
  '.e2e-test-collection-summary-tile-title';

export class CollectionEditor extends BaseUser {
  /**
   * Navigates to the creator dashboard page.
   */
  async navigateToCreatorDashboardPage(): Promise<void> {
    await this.goto(creatorDashboardUrl);
    showMessage('Navigated to creator dashboard page.');
  }

  /**
   * Clicks the "Create" activity button on the creator dashboard.
   */
  async clickCreateActivityButton(): Promise<void> {
    await this.page.waitForSelector(createActivityButtonSelector);
    await this.clickOnElementWithSelector(createActivityButtonSelector);
    showMessage('Clicked create activity button.');
  }

  /**
   * Clicks the "Create Collection" button in the activity creation modal.
   * After clicking, the page navigates to the collection editor via
   * window.location.href, so we wait for navigation to complete.
   */
  async clickCreateCollectionButton(): Promise<void> {
    await this.page.waitForSelector(createCollectionButtonSelector, {
      visible: true,
    });
    const navigationPromise = this.page.waitForNavigation({
      waitUntil: ['networkidle2', 'load'],
    });
    await this.clickOnElementWithSelector(createCollectionButtonSelector);
    await navigationPromise;
    await this.page.waitForSelector(collectionEditorCardsContainerSelector, {
      visible: true,
    });
    showMessage('Clicked create collection button.');
  }

  /**
   * Creates a new collection by navigating to the creator dashboard and
   * clicking through the collection creation flow.
   */
  async createNewCollection(): Promise<void> {
    await this.navigateToCreatorDashboardPage();
    await this.clickCreateActivityButton();
    await this.clickCreateCollectionButton();
    showMessage('Started creating a new collection.');
  }

  /**
   * Adds an existing exploration to the collection by entering its ID.
   * @param {string} explorationId - The ID of the exploration to add.
   */
  async addExistingExploration(explorationId: string): Promise<void> {
    // Count existing nodes before adding.
    const existingNodes = await this.page.$$(editorDeleteNodeSelector);
    const expectedNodeCount = existingNodes.length + 1;

    await this.page.waitForSelector(addExplorationInputSelector, {
      visible: true,
    });
    await this.clearAllTextFrom(addExplorationInputSelector);
    await this.typeInInputField(addExplorationInputSelector, explorationId);

    // Wait until the button becomes active after debouncing.
    await this.page.waitForSelector(
      `${addExplorationButtonSelector}:not([disabled])`,
      {visible: true}
    );
    await this.clickOnElementWithSelector(addExplorationButtonSelector);

    // Wait for the new node to appear in the DOM.
    await this.page.waitForFunction(
      (selector: string, count: number) => {
        return document.querySelectorAll(selector).length >= count;
      },
      {},
      editorDeleteNodeSelector,
      expectedNodeCount
    );
    showMessage(`Added exploration with ID: ${explorationId}.`);
  }

  /**
   * Shifts a node to the left in the collection node graph.
   * @param {number} nodeIndex - The zero-based index of the node to shift.
   */
  async shiftNodeLeft(nodeIndex: number): Promise<void> {
    const shiftLeftButtons = await this.page.$$(editorShiftLeftSelector);
    if (nodeIndex >= shiftLeftButtons.length) {
      throw new Error(
        `Cannot shift node at index ${nodeIndex} left. ` +
          `Only ${shiftLeftButtons.length} shift-left buttons found.`
      );
    }
    await shiftLeftButtons[nodeIndex].evaluate(el =>
      (el as HTMLElement).click()
    );
    showMessage(`Shifted node at index ${nodeIndex} to the left.`);
  }

  /**
   * Shifts a node to the right in the collection node graph.
   * @param {number} nodeIndex - The zero-based index of the node to shift.
   */
  async shiftNodeRight(nodeIndex: number): Promise<void> {
    const shiftRightButtons = await this.page.$$(editorShiftRightSelector);
    if (nodeIndex >= shiftRightButtons.length) {
      throw new Error(
        `Cannot shift node at index ${nodeIndex} right. ` +
          `Only ${shiftRightButtons.length} shift-right buttons found.`
      );
    }
    await shiftRightButtons[nodeIndex].evaluate(el =>
      (el as HTMLElement).click()
    );
    showMessage(`Shifted node at index ${nodeIndex} to the right.`);
  }

  /**
   * Deletes a node from the collection node graph.
   * @param {number} nodeIndex - The zero-based index of the node to delete.
   */
  async deleteNode(nodeIndex: number): Promise<void> {
    const deleteButtons = await this.page.$$(editorDeleteNodeSelector);
    if (nodeIndex >= deleteButtons.length) {
      throw new Error(
        `Cannot delete node at index ${nodeIndex}. ` +
          `Only ${deleteButtons.length} delete buttons found.`
      );
    }
    await deleteButtons[nodeIndex].evaluate(el => (el as HTMLElement).click());
    showMessage(`Deleted node at index ${nodeIndex}.`);
  }

  /**
   * Saves the current draft of the collection.
   */
  async saveDraft(): Promise<void> {
    await this.page.waitForSelector(
      `${saveDraftButtonSelector}:not([disabled])`
    );
    // Use JavaScript click to bypass any overlay issues (e.g., toast messages).
    await this.page.$eval(saveDraftButtonSelector, (button: Element) =>
      (button as HTMLButtonElement).click()
    );
    showMessage('Clicked save draft button.');
  }

  /**
   * Closes the save modal by clicking the confirm button.
   */
  async closeSaveModal(): Promise<void> {
    await this.page.waitForSelector(saveModalSelector, {visible: true});
    await this.page.waitForSelector(closeSaveModalButtonSelector, {
      visible: true,
    });
    await this.clickOnElementWithSelector(closeSaveModalButtonSelector);
    await this.page.waitForSelector(closeSaveModalButtonSelector, {
      hidden: true,
    });
    showMessage('Closed save modal.');
  }

  /**
   * Sets a commit message in the save modal.
   * @param {string} message - The commit message to set.
   */
  async setCommitMessage(message: string): Promise<void> {
    await this.page.waitForSelector(saveModalSelector, {visible: true});
    await this.page.waitForSelector(commitMessageInputSelector, {
      visible: true,
    });
    await this.clearAllTextFrom(commitMessageInputSelector);
    await this.typeInInputField(commitMessageInputSelector, message);
    showMessage(`Set commit message: "${message}".`);
  }

  /**
   * Clicks the publish button for the collection. Uses JavaScript click
   * to bypass any overlay issues (e.g., toast messages).
   */
  async publishCollection(): Promise<void> {
    await this.page.waitForSelector(
      `${editorPublishButtonSelector}:not([disabled])`
    );
    // Use JavaScript click to bypass any overlay issues (e.g., toast messages).
    await this.page.$eval(editorPublishButtonSelector, (button: Element) =>
      (button as HTMLButtonElement).click()
    );
    showMessage('Clicked publish collection button.');
  }

  /**
   * Sets the title in the pre-publish modal.
   * @param {string} title - The title for the collection.
   */
  async setTitle(title: string): Promise<void> {
    await this.page.waitForSelector(collectionTitleInputSelector, {
      visible: true,
    });
    await this.clearAllTextFrom(collectionTitleInputSelector);
    await this.typeInInputField(collectionTitleInputSelector, title);
    showMessage(`Set collection title: "${title}".`);
  }

  /**
   * Sets the objective in the pre-publish modal.
   * @param {string} objective - The objective for the collection.
   */
  async setObjective(objective: string): Promise<void> {
    await this.page.waitForSelector(collectionObjectiveInputSelector, {
      visible: true,
    });
    await this.clearAllTextFrom(collectionObjectiveInputSelector);
    await this.typeInInputField(collectionObjectiveInputSelector, objective);
    showMessage(`Set collection objective: "${objective}".`);
  }

  /**
   * Sets the category in the pre-publish modal by clicking on the dropdown
   * and selecting the matching option.
   * @param {string} category - The category to select.
   */
  async setCategory(category: string): Promise<void> {
    await this.page.waitForSelector(collectionCategoryDropdownSelector, {
      visible: true,
    });
    await this.clickOnElementWithSelector(collectionCategoryDropdownSelector);
    // Wait for the mat-option elements to be visible.
    await this.page.waitForSelector('.mat-option-text', {visible: true});
    const optionElements = await this.page.$$('.mat-option-text');
    for (const option of optionElements) {
      const text = await this.page.evaluate(
        (el: Element) => (el as HTMLElement).innerText.trim(),
        option
      );
      if (text === category) {
        await option.evaluate(el => (el as HTMLElement).click());
        showMessage(`Set collection category: "${category}".`);
        return;
      }
    }
    throw new Error(`Category "${category}" not found in dropdown.`);
  }

  /**
   * Clicks the "Save Changes" button in the pre-publish modal to finalize
   * publishing the collection.
   */
  async saveChanges(): Promise<void> {
    await this.page.waitForSelector(
      `${collectionSaveChangesButtonSelector}:not([disabled])`
    );
    await this.clickOnElementWithSelector(collectionSaveChangesButtonSelector);
    // Wait for the modal to close.
    await this.page.waitForSelector(collectionSaveChangesButtonSelector, {
      hidden: true,
    });
    // Wait for save-in-progress to complete.
    await this.page.waitForSelector(saveInProgressLabelSelector, {
      hidden: true,
    });
    showMessage('Saved changes and published collection.');
  }

  /**
   * Navigates to the community library page.
   */
  async navigateToCommunityLibraryPage(): Promise<void> {
    await this.goto(communityLibraryUrl);
    showMessage('Navigated to community library page.');
  }

  /**
   * Searches for a collection in the community library.
   * @param {string} collectionTitle - The title of the collection to search.
   */
  async searchForCollection(collectionTitle: string): Promise<void> {
    await this.page.waitForSelector(searchInputSelector, {visible: true});
    await this.clickOnElementWithSelector(searchInputSelector);
    await this.typeInInputField(searchInputSelector, collectionTitle);
    await this.page.keyboard.press('Enter');
    await this.waitForPageToFullyLoad();
    showMessage(`Searched for collection: "${collectionTitle}".`);
  }

  /**
   * Plays a collection from the community library by clicking on its
   * summary tile.
   * @param {string} collectionTitle - The title of the collection to play.
   */
  async playCollection(collectionTitle: string): Promise<void> {
    await this.page.waitForSelector(collectionSummaryTileSelector, {
      visible: true,
    });

    const titleElements = await this.page.$$(
      collectionSummaryTileTitleSelector
    );
    for (const titleElement of titleElements) {
      const text = await this.page.evaluate(
        (el: Element) => (el as HTMLElement).innerText.trim(),
        titleElement
      );
      if (text === collectionTitle) {
        // Click the parent anchor/tile element.
        await titleElement.evaluate(el => {
          const tile = el.closest('a') || el.closest('mat-card') || el;
          (tile as HTMLElement).click();
        });
        await this.waitForPageToFullyLoad();
        showMessage(`Playing collection: "${collectionTitle}".`);
        return;
      }
    }
    throw new Error(
      `Collection "${collectionTitle}" not found in the library.`
    );
  }

  /**
   * Creates, fills metadata, and publishes a collection end-to-end.
   * @param {string} title - The title for the collection.
   * @param {string} objective - The objective for the collection.
   * @param {string} category - The category for the collection.
   * @param {string[]} explorationIds - The IDs of explorations to add.
   */
  async createAndPublishCollection(
    title: string,
    objective: string,
    category: string,
    explorationIds: string[]
  ): Promise<void> {
    await this.createNewCollection();
    for (const explorationId of explorationIds) {
      await this.addExistingExploration(explorationId);
    }
    await this.saveDraft();
    await this.closeSaveModal();
    await this.publishCollection();
    await this.setTitle(title);
    await this.setObjective(objective);
    await this.setCategory(category);
    await this.saveChanges();
    showMessage(`Created and published collection: "${title}".`);
  }
}

export const CollectionEditorFactory = (): CollectionEditor =>
  new CollectionEditor();
