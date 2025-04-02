// API Test Functions

// Test Civitai API connection
async function testCivitaiConnection() {
  try {
    const response = await fetch('/api/civitai/test-connection');
    const data = await response.json();

    const statusElement = document.getElementById('api-status');
    if (!statusElement) return;

    if (data.status === 'success') {
      statusElement.textContent = '✅ API Connection Normal';
      statusElement.className = 'success';

      // Display found model
      if (data.sample_model) {
        statusElement.textContent += ` - Sample Model: ${data.sample_model}`;
      }
    } else if (data.status === 'warning') {
      statusElement.textContent = '⚠️ API Connected, but no models found';
      statusElement.className = 'warning';
    } else {
      statusElement.textContent = '❌ API Connection Failed: ' + data.message;
      statusElement.className = 'error';
    }

    // Display API key status
    const apiKeyStatus = document.getElementById('api-key-status');
    if (apiKeyStatus) {
      apiKeyStatus.textContent = data.has_api_key
        ? '✅ API Key Set'
        : '❌ API Key Not Set';
      apiKeyStatus.className = data.has_api_key ? 'success' : 'error';
    }
  } catch (error) {
    console.error('Error testing API connection:', error);
    const statusElement = document.getElementById('api-status');
    if (statusElement) {
      statusElement.textContent = '❌ Request Failed: ' + error.message;
      statusElement.className = 'error';
    }
  }
}

// Set API key
async function setApiKey(apiKey) {
  try {
    const response = await fetch('/api/civitai/api-key', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ api_key: apiKey })
    });

    const data = await response.json();
    alert(data.message);

    // Update API key field in global settings
    const apiKeyInput = document.getElementById('api-key');
    if (apiKeyInput) {
      apiKeyInput.value = apiKey;
    }

    // Test connection again
    await testCivitaiConnection();
  } catch (error) {
    console.error('Error setting API key:', error);
    alert('Failed to set API key: ' + error.message);
  }
}

// Add API test area when page loads
document.addEventListener('DOMContentLoaded', () => {
  // Only add to settings page
  if (!document.getElementById('settings-form')) return;

  // Create API test area
  const testArea = document.createElement('div');
  testArea.className = 'api-test-area';
  testArea.innerHTML = `
        <h3>API Connection Test</h3>
        <div class="api-status-container">
            <div class="status-item">
                <span>API Connection Status:</span>
                <span id="api-status">Not Tested</span>
            </div>
            <div class="status-item">
                <span>API Key Status:</span>
                <span id="api-key-status">Unknown</span>
            </div>
        </div>
        <div class="api-test-actions">
            <button type="button" id="test-api-btn">Test API Connection</button>
            <div class="quick-api-key">
                <input type="text" id="quick-api-key" placeholder="Enter API Key...">
                <button type="button" id="set-api-key-btn">Quick Set</button>
            </div>
        </div>
    `;

  // Add before settings form
  const settingsForm = document.getElementById('settings-form');
  settingsForm.parentNode.insertBefore(testArea, settingsForm);

  // Add styles
  const styleEl = document.createElement('style');
  styleEl.textContent = `
        .api-test-area {
            margin: 20px 0;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background-color: #f9f9f9;
        }
        .api-status-container {
            margin: 15px 0;
        }
        .status-item {
            margin: 10px 0;
            display: flex;
            align-items: center;
        }
        .status-item span:first-child {
            min-width: 120px;
            font-weight: bold;
        }
        .success { color: green; }
        .warning { color: orange; }
        .error { color: red; }
        .api-test-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }
        .quick-api-key {
            display: flex;
            gap: 5px;
        }
        #quick-api-key {
            width: 250px;
        }
    `;
  document.head.appendChild(styleEl);

  // Add event listeners
  document.getElementById('test-api-btn').addEventListener('click', testCivitaiConnection);
  document.getElementById('set-api-key-btn').addEventListener('click', () => {
    const apiKey = document.getElementById('quick-api-key').value.trim();
    if (apiKey) {
      setApiKey(apiKey);
    } else {
      alert('Please enter a valid API key');
    }
  });

  // Automatically test connection
  testCivitaiConnection();
}); 