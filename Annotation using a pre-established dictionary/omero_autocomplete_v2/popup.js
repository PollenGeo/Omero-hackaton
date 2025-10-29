// Load current data when popup opens
document.addEventListener('DOMContentLoaded', function() {
  chrome.storage.local.get(['speciesList'], function(result) {
    const loadedCount = document.getElementById('loadedCount');
    if (result.speciesList && result.speciesList.length > 0) {
      loadedCount.textContent = `${result.speciesList.length} species loaded`;
    } else {
      loadedCount.textContent = 'No species loaded';
    }
  });
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ isActive: true }, function() {
    console.log("Autocomplete set to active on installation");
  });
});

// Initialize button state
let isActive = true;

// Get button element
const toggleButton = document.getElementById('toggleButton');

// Load initial state
chrome.storage.local.get(['isActive'], function(result) {
  isActive = result.isActive !== undefined ? result.isActive : true;
  updateButtonState();
});

// Update button appearance based on state
function updateButtonState() {
  toggleButton.textContent = isActive ? 'Autocomplete Active' : 'Autocomplete Inactive';
  toggleButton.style.backgroundColor = isActive ? "#32b838" : "#ca2121";
  toggleButton.classList.toggle('inactive', !isActive);

}

// Handle button click
toggleButton.addEventListener('click', function() {
  isActive = !isActive;
  
  // Update storage
  chrome.storage.local.set({ isActive: isActive }, function() {
    console.log('Autocomplete state updated:', isActive);
    updateButtonState();
  });
});


function parseCSV(text, separator) {
  /* This function reads a headerless csv file with a single column containing species names
     and removes any duplicates
  */

  // Split into lines and remove empty lines
  const lines = text.split(/\r?\n/).filter(line => line.trim());
  if (lines.length === 0) {
    throw new Error('CSV file cannot be empty');
  }

  // Process each row
  const speciesList = [];
  const previewData = [];

  for (let i = 0; i < lines.length; i++) {
    // Handle quoted values properly
    const row = lines[i].split(separator).map(cell => cell.trim().replace(/^["']|["']$/g, ''));
    
    // Verify single column format
    if (row.length !== 1) {
      throw new Error('CSV must contain exactly one column with species names');
    }
    
    if (row[0]) {  // Check if the species name exists and is not empty
      speciesList.push(row[0]);
      if (previewData.length < 15) {  // Store first 15 rows for preview
        previewData.push(row);
      }
    }
  }

  return {
    speciesList: [...new Set(speciesList)], // Remove duplicates
    headers: ['Species'], // Add a default header for the preview table
    preview: previewData
  };
}

function createPreviewTable(headers, previewData) {
  let table = '<table class="preview-table">';
  
  /* This function creates the preview table from the given file
    where the user checks is the file is correctly uploaded,
    is like printing the head of a df in python or R
*/
  // Add header
  table += '<tr>';
  headers.forEach(header => {
    table += `<th>${header}</th>`;
  });
  table += '</tr>';
  
  // Add preview rows
  previewData.forEach(row => {
    table += '<tr>';
    row.forEach(cell => {
      table += `<td>${cell}</td>`;
    });
    table += '</tr>';
  });
  
  table += '</table>';
  return table;
}

let lastFile = null;

document.getElementById('fileInput').addEventListener('change', function(e) {
  lastFile = e.target.files[0];
  if (lastFile) {
    processFile();
  }
});

document.getElementById('separatorSelect').addEventListener('change', function() {
  if (lastFile) {
    processFile();
  }
});

function processFile() {
  const status = document.getElementById('status');
  const preview = document.getElementById('preview');
  const previewSection = document.getElementById('previewSection');
  const loadedCount = document.getElementById('loadedCount');
  const separator = document.getElementById('separatorSelect').value;
  
  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const result = parseCSV(e.target.result, separator);
      
      // Show preview
      preview.innerHTML = createPreviewTable(result.headers, result.preview);
      previewSection.style.display = 'block';
      
      // Save to storage

      chrome.storage.local.set({ speciesList: result.speciesList }, function() {
        status.textContent = `Loaded ${result.speciesList.length} unique species names`;
        status.className = '';
        loadedCount.textContent = `${result.speciesList.length} species loaded`;
      });


    } catch (error) {
      status.textContent = error.message;
      status.className = 'error';
      previewSection.style.display = 'none';
    }
  };
  reader.readAsText(lastFile);
}