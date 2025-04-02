// Global state
const state = {
  currentPage: 1,
  totalPages: 1,
  searchQuery: "",
  selectedTypes: [],
  selectedBaseModels: [],
  sortBy: "Most Downloaded",
  showNsfw: false,
  downloads: [],
  downloadRefreshInterval: null,
  currentRefreshRate: 'slow'
};

// DOM elements
const elements = {
  // Navigation
  navLinks: document.querySelectorAll('nav a'),
  pages: document.querySelectorAll('.page'),

  // Search and filters
  searchInput: document.getElementById('search-input'),
  searchButton: document.getElementById('search-button'),
  modelTypeSelect: document.getElementById('model-type'),
  baseModelSelect: document.getElementById('base-model'),
  sortBySelect: document.getElementById('sort-by'),
  showNsfwCheckbox: document.getElementById('show-nsfw'),

  // Pagination
  prevPageButton: document.getElementById('prev-page'),
  nextPageButton: document.getElementById('next-page'),
  pageInfo: document.getElementById('page-info'),

  // Results
  resultsContainer: document.getElementById('results-container'),

  // Downloads
  queueContainer: document.getElementById('queue-container'),

  // Settings
  settingsForm: document.getElementById('settings-form'),
  apiKeyInput: document.getElementById('api-key'),
  modelDirInput: document.getElementById('model-dir'),
  useAria2Checkbox: document.getElementById('use-aria2'),
  aria2FlagsInput: document.getElementById('aria2-flags'),
  createJsonCheckbox: document.getElementById('create-json'),
  saveImagesCheckbox: document.getElementById('save-images'),
  imageDirInput: document.getElementById('image-dir'),
  useProxyCheckbox: document.getElementById('use-proxy'),
  proxyUrlInput: document.getElementById('proxy-url'),
  disableDnsCheckbox: document.getElementById('disable-dns'),

  // Modal
  modelModal: document.getElementById('model-modal'),
  closeModal: document.querySelector('.close'),
  modelDetails: document.getElementById('model-details')
};

// Initialize the application
async function init() {
  // Set up event listeners
  setupEventListeners();

  // Load model types and base models
  await Promise.all([
    loadModelTypes(),
    loadBaseModels()
  ]);

  // Load settings
  await loadSettings();

  // Start with a search
  await searchModels();

  // Perform an initial refresh
  refreshDownloads();

  // Decide whether to start auto-refresh based on current page
  if (document.querySelector('.page.active').id === 'downloads') {
    startDownloadRefresh();
  }
}

// Set up event listeners
function setupEventListeners() {
  // Navigation
  elements.navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const target = e.target.getAttribute('data-page');
      showPage(target);
    });
  });

  // Search
  elements.searchButton.addEventListener('click', () => {
    state.currentPage = 1;
    searchModels();
  });

  elements.searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      state.currentPage = 1;
      searchModels();
    }
  });

  // Filters
  elements.modelTypeSelect.addEventListener('change', () => {
    state.selectedTypes = Array.from(elements.modelTypeSelect.selectedOptions).map(option => option.value).filter(Boolean);
    state.currentPage = 1;
    searchModels();
  });

  elements.baseModelSelect.addEventListener('change', () => {
    state.selectedBaseModels = Array.from(elements.baseModelSelect.selectedOptions).map(option => option.value).filter(Boolean);
    state.currentPage = 1;
    searchModels();
  });

  elements.sortBySelect.addEventListener('change', () => {
    state.sortBy = elements.sortBySelect.value;
    state.currentPage = 1;
    searchModels();
  });

  elements.showNsfwCheckbox.addEventListener('change', () => {
    state.showNsfw = elements.showNsfwCheckbox.checked;
    state.currentPage = 1;
    searchModels();
  });

  // Pagination
  elements.prevPageButton.addEventListener('click', () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      searchModels();
    }
  });

  elements.nextPageButton.addEventListener('click', () => {
    if (state.currentPage < state.totalPages) {
      state.currentPage++;
      searchModels();
    }
  });

  // Settings form
  elements.settingsForm.addEventListener('submit', (e) => {
    e.preventDefault();
    saveSettings();
  });

  // Conditional display for proxy settings
  elements.useProxyCheckbox.addEventListener('change', () => {
    document.getElementById('proxy-url-group').style.display =
      elements.useProxyCheckbox.checked ? 'block' : 'none';
  });

  // Conditional display for aria2 settings
  elements.useAria2Checkbox.addEventListener('change', () => {
    document.getElementById('aria2-flags-group').style.display =
      elements.useAria2Checkbox.checked ? 'block' : 'none';
  });

  // Conditional display for image directory settings
  elements.saveImagesCheckbox.addEventListener('change', () => {
    document.getElementById('image-dir-group').style.display =
      elements.saveImagesCheckbox.checked ? 'block' : 'none';
  });

  // Modal close button
  elements.closeModal.addEventListener('click', () => {
    elements.modelModal.style.display = 'none';
  });

  // Close modal when clicking outside
  window.addEventListener('click', (e) => {
    if (e.target === elements.modelModal) {
      elements.modelModal.style.display = 'none';
    }
  });
}

// Show a specific page
function showPage(pageId) {
  elements.navLinks.forEach(link => {
    link.classList.toggle('active', link.getAttribute('data-page') === pageId);
  });

  elements.pages.forEach(page => {
    page.classList.toggle('active', page.id === pageId);
  });

  // Manage download refresh based on page type
  if (pageId === 'downloads') {
    // When switching to downloads page, refresh immediately and start auto-refresh
    refreshDownloads();
    startDownloadRefresh();
  } else {
    // When switching to other pages, stop auto-refresh to save resources
    if (state.downloadRefreshInterval) {
      clearInterval(state.downloadRefreshInterval);
      state.downloadRefreshInterval = null;
    }
  }
}

// Load model types from API
async function loadModelTypes() {
  try {
    const response = await fetch('/api/models/types');
    if (!response.ok) {
      throw new Error(`API returned ${response.status}: ${response.statusText}`);
    }

    const types = await response.json();

    // Check if types is an array
    if (!Array.isArray(types)) {
      console.error('Model types response is not an array:', types);
      return;
    }

    // Clear existing options
    elements.modelTypeSelect.innerHTML = '<option value="">All Types</option>';

    // Add new options
    types.forEach(type => {
      const option = document.createElement('option');
      option.value = type;
      option.textContent = type;
      elements.modelTypeSelect.appendChild(option);
    });
  } catch (error) {
    console.error('Error loading model types:', error);
  }
}

// Load base models from API
async function loadBaseModels() {
  try {
    const response = await fetch('/api/models/basemodels');
    if (!response.ok) {
      throw new Error(`API returned ${response.status}: ${response.statusText}`);
    }

    const baseModels = await response.json();

    // Check if baseModels is an array
    if (!Array.isArray(baseModels)) {
      console.error('Base models response is not an array:', baseModels);
      return;
    }

    // Clear existing options
    elements.baseModelSelect.innerHTML = '<option value="">All Base Models</option>';

    // Add new options
    baseModels.forEach(model => {
      const option = document.createElement('option');
      option.value = model;
      option.textContent = model;
      elements.baseModelSelect.appendChild(option);
    });
  } catch (error) {
    console.error('Error loading base models:', error);
  }
}

// Search for models
async function searchModels() {
  try {
    // Show loading state
    elements.resultsContainer.innerHTML = '<div class="loading">Loading models...</div>';

    // Build query parameters
    const params = new URLSearchParams({
      page: state.currentPage,
      page_size: 20,
      sort: state.sortBy,
      nsfw: state.showNsfw
    });

    // Add search query if present
    if (elements.searchInput.value) {
      params.append('query', elements.searchInput.value);
    }

    // Add selected types if any
    if (state.selectedTypes.length > 0) {
      state.selectedTypes.forEach(type => {
        params.append('type', type);
      });
    }

    // Add selected base models if any
    if (state.selectedBaseModels.length > 0) {
      state.selectedBaseModels.forEach(model => {
        params.append('base_model', model);
      });
    }

    // Make the API request
    const response = await fetch(`/api/models/search?${params.toString()}`);

    if (!response.ok) {
      throw new Error(`API returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();

    // Check if data has the expected format
    if (!data || !data.metadata || !data.items) {
      throw new Error('Invalid response format from API');
    }

    // Update state
    state.totalPages = data.metadata.totalPages || 1;

    // Update pagination
    elements.pageInfo.textContent = `Page ${state.currentPage} of ${state.totalPages}`;
    elements.prevPageButton.disabled = state.currentPage <= 1;
    elements.nextPageButton.disabled = state.currentPage >= state.totalPages;

    // Render results
    renderSearchResults(data.items);
  } catch (error) {
    console.error('Error searching models:', error);
    elements.resultsContainer.innerHTML = '<div class="error">Error loading models. Please try again.</div>';
  }
}

// Render search results
function renderSearchResults(models) {
  if (!models || models.length === 0) {
    elements.resultsContainer.innerHTML = '<div class="no-results">No models found. Try different search criteria.</div>';
    return;
  }

  // Clear results container
  elements.resultsContainer.innerHTML = '';

  // Create model cards
  models.forEach(model => {
    const card = document.createElement('div');
    card.className = `model-card ${model.nsfw ? 'nsfw' : ''}`;

    // Get the primary image from the first version if available
    let imageUrl = '/static/img/no-image.jpg';
    if (model.modelVersions && model.modelVersions.length > 0) {
      const version = model.modelVersions[0];
      if (version.images && version.images.length > 0) {
        imageUrl = version.images[0].url;
      }
    }

    card.innerHTML = `
            <div class="card-image">
                <img src="${imageUrl}" alt="${model.name}">
                ${model.nsfw ? '<span class="nsfw-badge">NSFW</span>' : ''}
            </div>
            <div class="card-content">
                <h3 title="${model.name}">${model.name}</h3>
                <div class="card-meta">
                    <span>${model.type}</span>
                    <span>${model.modelVersions[0]?.baseModel || 'N/A'}</span>
                </div>
                <div class="card-actions">
                    <button class="view-btn" data-id="${model.id}">View Details</button>
                    <button class="download-btn" data-id="${model.id}">Download</button>
                </div>
            </div>
        `;

    // Add event listeners
    card.querySelector('.view-btn').addEventListener('click', () => {
      showModelDetails(model.id);
    });

    card.querySelector('.download-btn').addEventListener('click', () => {
      downloadModel(model.id);
    });

    elements.resultsContainer.appendChild(card);
  });
}

// Show model details
async function showModelDetails(modelId) {
  try {
    // Show loading state in modal
    elements.modelDetails.innerHTML = '<div class="loading">Loading model details...</div>';
    elements.modelModal.style.display = 'block';

    // Fetch model details
    const response = await fetch(`/api/models/${modelId}`);
    const model = await response.json();

    // Create model details HTML
    let html = `
            <div class="model-header">
                <h2>${model.name}</h2>
                ${model.nsfw ? '<span class="nsfw-badge">NSFW</span>' : ''}
            </div>
        `;

    // Model gallery
    if (model.modelVersions && model.modelVersions.length > 0) {
      const version = model.modelVersions[0];
      if (version.images && version.images.length > 0) {
        html += '<div class="model-gallery">';

        version.images.forEach(image => {
          html += `<img src="${image.url}" alt="" class="gallery-image">`;
        });

        html += '</div>';
      }
    }

    // Model description
    if (model.description) {
      html += `<div class="model-description">${model.description}</div>`;
    }

    // Model metadata
    html += `
            <div class="model-meta">
                <div class="meta-item">Type: ${model.type}</div>
                ${model.tags && model.tags.length > 0 ? `<div class="meta-item">Tags: ${model.tags.join(', ')}</div>` : ''}
            </div>
        `;

    // Model versions
    if (model.modelVersions && model.modelVersions.length > 0) {
      html += '<div class="model-versions">';
      html += '<h3>Versions</h3>';

      model.modelVersions.forEach(version => {
        html += `
                    <div class="version-item">
                        <div class="version-header">
                            <h4>${version.name}</h4>
                            <span>Base Model: ${version.baseModel}</span>
                        </div>
                `;

        if (version.trainedWords && version.trainedWords.length > 0) {
          html += `<div>Trained Words: ${version.trainedWords.join(', ')}</div>`;
        }

        if (version.files && version.files.length > 0) {
          html += '<div class="version-files">';
          html += '<h5>Files</h5>';

          version.files.forEach(file => {
            const fileSize = formatFileSize(file.size);
            html += `
                            <div class="file-item">
                                <div>
                                    <div>${file.name} ${file.primary ? '(Primary)' : ''}</div>
                                    <div>Size: ${fileSize}</div>
                                </div>
                                <button class="download-file-btn" data-model-id="${model.id}" data-version-id="${version.id}" data-file-id="${file.id}">Download</button>
                            </div>
                        `;
          });

          html += '</div>';
        }

        html += '</div>';
      });

      html += '</div>';
    }

    // Update modal content
    elements.modelDetails.innerHTML = html;

    // Add event listeners to download buttons
    const downloadButtons = elements.modelDetails.querySelectorAll('.download-file-btn');
    downloadButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        const modelId = parseInt(e.target.getAttribute('data-model-id'));
        const versionId = parseInt(e.target.getAttribute('data-version-id'));
        const fileId = parseInt(e.target.getAttribute('data-file-id'));

        downloadModelFile(modelId, versionId, fileId);
        elements.modelModal.style.display = 'none';
      });
    });
  } catch (error) {
    console.error('Error loading model details:', error);
    elements.modelDetails.innerHTML = '<div class="error">Error loading model details. Please try again.</div>';
  }
}

// Format file size
function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));

  return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + units[i];
}

// Check if download feature is enabled
function isDownloadEnabled() {
  // Currently downloads are disabled
  return false;
}

// Download a model (uses the primary file of the first version)
async function downloadModel(modelId) {
  // Check if downloads are enabled
  if (!isDownloadEnabled()) {
    alert('Downloads are temporarily disabled. This feature is under construction. Please check back later.');
    showPage('downloads');
    return;
  }

  try {
    const response = await fetch('/api/download', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_id: modelId
      })
    });

    if (!response.ok) {
      throw new Error('Failed to start download');
    }

    const task = await response.json();

    // Show success message
    alert(`Download for "${task.model_name}" has been added to the queue.`);

    // Switch to downloads tab
    showPage('downloads');
  } catch (error) {
    console.error('Error downloading model:', error);
    alert('Error downloading model. Please try again.');
  }
}

// Download a specific file from a model version
async function downloadModelFile(modelId, versionId, fileId) {
  // Check if downloads are enabled
  if (!isDownloadEnabled()) {
    alert('Downloads are temporarily disabled. This feature is under construction. Please check back later.');
    showPage('downloads');
    return;
  }

  try {
    const response = await fetch('/api/downloads', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model_id: modelId,
        version_id: versionId,
        file_id: fileId
      })
    });

    if (!response.ok) {
      throw new Error('Failed to start download');
    }

    const task = await response.json();

    // Show success message
    alert(`Download for "${task.model_name}" has been added to the queue.`);

    // Switch to downloads tab
    showPage('downloads');
  } catch (error) {
    console.error('Error downloading model file:', error);
    alert('Error downloading model file. Please try again.');
  }
}

// Refresh downloads list
async function refreshDownloads() {
  try {
    console.log('Refreshing download queue...');
    const response = await fetch('/api/downloads');
    if (!response.ok) {
      console.error('API error:', response.status, response.statusText);
      return;
    }

    const downloads = await response.json();
    console.log('Retrieved download queue:', downloads);

    if (downloads.length === 0) {
      console.log('Download queue is empty');
    } else {
      // Print status of each download task
      downloads.forEach(download => {
        console.log(`Task ${download.id}: ${download.status}, progress: ${download.progress}%, file: ${download.filename}`);
        if (download.error) {
          console.error(`Download error: ${download.error}`);
        }
      });
    }

    // Update state
    state.downloads = downloads;

    // Render downloads
    renderDownloads(downloads);
  } catch (error) {
    console.error('Error refreshing download queue:', error);
  }
}

// Start automatic refresh of download queue
function startDownloadRefresh() {
  // Clear any existing interval
  if (state.downloadRefreshInterval) {
    clearInterval(state.downloadRefreshInterval);
  }

  // Refresh immediately
  refreshDownloads();

  // Set refresh interval
  const checkAndAdjustRefreshRate = () => {
    // Check if there are active downloads
    const hasActiveDownloads = state.downloads && state.downloads.some(
      download => ['queued', 'downloading', 'active'].includes(download.status)
    );

    if (hasActiveDownloads) {
      // If there are active downloads, use a shorter refresh interval
      if (state.currentRefreshRate !== 'fast') {
        console.log('Switching to fast refresh mode: 500ms');
        clearInterval(state.downloadRefreshInterval);
        state.downloadRefreshInterval = setInterval(refreshDownloads, 500); // Refresh every 0.5 seconds
        state.currentRefreshRate = 'fast';
      }
    } else {
      // If there are no active downloads, use a longer refresh interval
      if (state.currentRefreshRate !== 'slow') {
        console.log('Switching to slow refresh mode: 3000ms');
        clearInterval(state.downloadRefreshInterval);
        state.downloadRefreshInterval = setInterval(refreshDownloads, 3000); // Refresh every 3 seconds
        state.currentRefreshRate = 'slow';
      }
    }
  };

  // Check immediately first
  checkAndAdjustRefreshRate();

  // Set up periodic check of refresh rate
  setInterval(checkAndAdjustRefreshRate, 5000); // Check every 5 seconds if refresh rate needs adjustment
}

// Render downloads list
function renderDownloads(downloads) {
  if (!downloads || downloads.length === 0) {
    elements.queueContainer.innerHTML = '<div class="no-downloads">No downloads in queue</div>';
    return;
  }

  console.log('Rendering download list:', downloads);

  // Clear container
  elements.queueContainer.innerHTML = '';

  // Create download items
  downloads.forEach(download => {
    const item = document.createElement('div');
    item.className = 'download-item';

    // Add status identifier
    let statusText = download.status;
    if (download.status === 'completed') {
      statusText = 'Completed';
    } else if (download.status === 'downloading') {
      statusText = 'Downloading';
    } else if (download.status === 'queued') {
      statusText = 'Queued';
    } else if (download.status === 'failed') {
      statusText = 'Failed';
    }

    // Add is_test identifier to filter test tasks
    if (download.is_test) {
      item.classList.add('test-task');
    }

    // Add is_recent identifier to mark recently completed tasks
    if (download.is_recent) {
      item.classList.add('is-recent');
    }

    // Format progress for display
    const progress = Math.min(Math.round(download.progress || 0), 100);

    // Add special class for aria2 downloads
    if (download.download_method === 'aria2' || download.aria2_gid) {
      item.classList.add('aria2-download');
    }

    // Calculate download speed and ETA if available
    let speedInfo = '';
    if (download.download_speed && download.download_speed > 0) {
      const speedMbps = (download.download_speed / (1024 * 1024)).toFixed(2);
      speedInfo = `<div class="download-speed">${speedMbps} MB/s</div>`;

      if (download.eta) {
        let etaDisplay = '';
        if (download.eta > 3600) {
          const hours = Math.floor(download.eta / 3600);
          const minutes = Math.floor((download.eta % 3600) / 60);
          etaDisplay = `${hours}h ${minutes}m`;
        } else {
          const etaMinutes = Math.floor(download.eta / 60);
          const etaSeconds = Math.floor(download.eta % 60);
          etaDisplay = `${etaMinutes}m ${etaSeconds}s`;
        }
        speedInfo += `<div class="download-eta">ETA: ${etaDisplay}</div>`;
      }
    }

    // Ensure filename display (use filename first, if not available use the last part of filepath)
    let displayFilename = download.filename || '';
    if (!displayFilename && download.file_path) {
      const pathParts = download.file_path.split('/');
      displayFilename = pathParts[pathParts.length - 1];
    }

    item.innerHTML = `
            <div class="download-info">
                <h3>${download.model_name || 'Unknown model'}</h3>
                <div class="download-meta">
                    <span>${download.model_type || ''}</span>
                    <span>${displayFilename}</span>
                    ${download.is_test ? '<span class="test-badge">(Test)</span>' : ''}
                    ${(download.download_method === 'aria2' || download.aria2_gid) ? '<span class="aria2-badge">aria2</span>' : ''}
                </div>
            </div>
            <div class="download-progress">
                <div class="progress-bar">
                    <div class="progress-bar-fill" style="width: ${progress}%"></div>
                </div>
                <div class="progress-text">
                    <span>${progress}%</span>
                    <span class="progress-time">${new Date().toLocaleTimeString()}</span>
                </div>
                ${speedInfo}
            </div>
            <div class="download-status status-${download.status}">${statusText}</div>
            <div class="download-actions">
                ${['queued', 'downloading', 'active'].includes(download.status) ? `<button class="cancel-btn" data-id="${download.id}">Cancel</button>` : ''}
                ${download.error ? `<div class="error-message">${download.error}</div>` : ''}
            </div>
        `;

    // Add event listener for cancel button
    const cancelBtn = item.querySelector('.cancel-btn');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        cancelDownload(download.id);
      });
    }

    elements.queueContainer.appendChild(item);
  });
}

// Cancel a download
async function cancelDownload(taskId) {
  try {
    const response = await fetch(`/api/downloads/${taskId}`, {
      method: 'DELETE'
    });

    if (!response.ok) {
      throw new Error('Failed to cancel download');
    }

    // Refresh downloads immediately
    refreshDownloads();
  } catch (error) {
    console.error('Error canceling download:', error);
    alert('Error canceling download. Please try again.');
  }
}

// Load settings from API
async function loadSettings() {
  try {
    const response = await fetch('/api/settings');
    const settings = await response.json();

    // Update form fields
    elements.apiKeyInput.value = settings.api_key || '';
    elements.modelDirInput.value = settings.model_dir || '';
    elements.useAria2Checkbox.checked = settings.download_with_aria2;
    elements.aria2FlagsInput.value = settings.aria2_flags || '';
    elements.createJsonCheckbox.checked = settings.create_model_json;
    elements.saveImagesCheckbox.checked = settings.save_images;
    elements.imageDirInput.value = settings.custom_image_dir || '';
    elements.useProxyCheckbox.checked = settings.use_proxy;
    elements.proxyUrlInput.value = settings.proxy_url || '';
    elements.disableDnsCheckbox.checked = settings.disable_dns_lookup;

    // Set state for NSFW content
    state.showNsfw = settings.show_nsfw;
    elements.showNsfwCheckbox.checked = settings.show_nsfw;

    // Update conditional displays
    document.getElementById('proxy-url-group').style.display =
      settings.use_proxy ? 'block' : 'none';
    document.getElementById('aria2-flags-group').style.display =
      settings.download_with_aria2 ? 'block' : 'none';
    document.getElementById('image-dir-group').style.display =
      settings.save_images ? 'block' : 'none';
  } catch (error) {
    console.error('Error loading settings:', error);
  }
}

// Save settings to API
async function saveSettings() {
  try {
    const settings = {
      api_key: elements.apiKeyInput.value,
      model_dir: elements.modelDirInput.value,
      download_with_aria2: elements.useAria2Checkbox.checked,
      aria2_flags: elements.aria2FlagsInput.value,
      show_nsfw: elements.showNsfwCheckbox.checked,
      create_model_json: elements.createJsonCheckbox.checked,
      save_images: elements.saveImagesCheckbox.checked,
      custom_image_dir: elements.imageDirInput.value,
      use_proxy: elements.useProxyCheckbox.checked,
      proxy_url: elements.proxyUrlInput.value,
      disable_dns_lookup: elements.disableDnsCheckbox.checked
    };

    const response = await fetch('/api/settings', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(settings)
    });

    if (!response.ok) {
      throw new Error('Failed to save settings');
    }

    // Show success message
    alert('Settings saved successfully');

    // Update state for NSFW content
    state.showNsfw = settings.show_nsfw;
  } catch (error) {
    console.error('Error saving settings:', error);
    alert('Error saving settings. Please try again.');
  }
}

// Clear download history function
async function clearDownloadHistory() {
  try {
    // Ask for confirmation
    if (!confirm('Are you sure you want to clear all completed download history? This action cannot be undone.')) {
      return;
    }

    const response = await fetch('/api/downloads/history', {
      method: 'DELETE'
    });

    if (!response.ok) {
      throw new Error('Failed to clear history');
    }

    // Refresh download list
    refreshDownloads();

    alert('Download history has been cleared');
  } catch (error) {
    console.error('Error clearing download history:', error);
    alert('Failed to clear download history: ' + error.message);
  }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', init); 