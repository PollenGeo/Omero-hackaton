let speciesList = [];
let currentInput = null;
let suggestionsDiv = null;
let isAutocompleteActive = true;

// Load initial state and species list
chrome.storage.local.get(['speciesList', 'isActive'], function(result) {
  speciesList = result.speciesList || [];
  isAutocompleteActive = result.isActive !== undefined ? result.isActive : true;
  console.log('Lista inicial de especies cargada:', speciesList.length, 'elementos');
});

// Listen for storage changes
chrome.storage.onChanged.addListener(function(changes, namespace) {
  if (namespace === 'local' && changes.speciesList) {
    speciesList = changes.speciesList.newValue || [];
    console.log('Lista de especies actualizada en content.js:', speciesList.length, 'elementos');
  }
  if (namespace === 'local' && changes.isActive !== undefined) {
    isAutocompleteActive = changes.isActive.newValue;
    console.log('Estado de autocompletar cambiado a:', isAutocompleteActive);
    if (!isAutocompleteActive && suggestionsDiv) {
      suggestionsDiv.style.display = 'none';
    }
  }
});

function createSuggestionsDiv() {
  if (suggestionsDiv) {
    document.body.removeChild(suggestionsDiv);
  }
  suggestionsDiv = document.createElement('div');
  suggestionsDiv.className = 'species-suggestions';
  suggestionsDiv.style.display = 'none';
  document.body.appendChild(suggestionsDiv);
  return suggestionsDiv;
}

function showSuggestions(input) {
  console.log("showSuggestions called with input:", input ? input.value : "no input");
  console.log("Current speciesList length:", speciesList.length);

  const value = input.value.toLowerCase().trim();
  if (!value || !speciesList.length) {
    if (suggestionsDiv) suggestionsDiv.style.display = 'none';
    console.log("No input value or empty speciesList");
    return;
  }

  if (!suggestionsDiv) {
    suggestionsDiv = createSuggestionsDiv();
  }

  const matches = speciesList
    .filter(species => species.toLowerCase().includes(value));

  console.log(`Found ${matches.length} matches for "${value}"`);
  console.log('First few matches:', matches.slice(0, 3));

  if (matches.length === 0) {
    suggestionsDiv.style.display = 'none';
    return;
  }

  // Retrieve last clicked suggestion and reorder matches
  chrome.storage.local.get(['lastClickedSuggestion'], (result) => {
    // Check if input value changed during async operation
    const currentValue = input.value.toLowerCase().trim();
    if (currentValue !== value) {
      console.log('Input value changed, not showing suggestions');
      suggestionsDiv.style.display = 'none';
      return;
    }

    const lastClicked = result.lastClickedSuggestion;
    let orderedMatches = [...matches];

    if (lastClicked) {
      const index = orderedMatches.indexOf(lastClicked);
      if (index !== -1) {
        orderedMatches.splice(index, 1);
        orderedMatches.unshift(lastClicked);
      }
    }

    // Position suggestions div
    const rect = input.getBoundingClientRect();
    suggestionsDiv.style.top = `${rect.bottom + window.scrollY}px`;
    suggestionsDiv.style.left = `${rect.left + window.scrollX}px`;
    suggestionsDiv.style.width = `${rect.width}px`;

    // Create suggestion items
    suggestionsDiv.innerHTML = orderedMatches
      .slice(0, 15)
      .map(species => `<div class="species-suggestion-item">${species}</div>`)
      .join('');

    suggestionsDiv.style.display = 'block';

    // Add click handlers
    suggestionsDiv.querySelectorAll('.species-suggestion-item').forEach(item => {
      item.addEventListener('click', function() {
        console.log('Suggestion clicked:', this.textContent);
        const selectedSpecies = this.textContent.trim();
        
        // Save last clicked suggestion
        chrome.storage.local.set({ lastClickedSuggestion: selectedSpecies });

        if (input) {
          input.value = "";
          for (let i = 0; i < selectedSpecies.length; i++) {
            setTimeout(() => {
              input.value += selectedSpecies[i];
              input.dispatchEvent(new KeyboardEvent('keyup', {
                key: selectedSpecies[i],
                code: `Key${selectedSpecies[i].toUpperCase()}`,
                keyCode: selectedSpecies.charCodeAt(i),
                bubbles: true
              }));
            }, i * 10);
          }
          input.dispatchEvent(new Event('input', { bubbles: true }));
          suggestionsDiv.style.display = 'none';
        }
      });
    });
  });
}

// Remaining functions (performAutocomplete, event listeners) remain unchanged
function performAutocomplete(input) {
  if (!input) {
    console.log("performAutocomplete called without valid input");
    return;
  }

  console.log("performAutocomplete called with input:", input.value);
  console.log("Current autocomplete state:", isAutocompleteActive);

  if (isAutocompleteActive) {
    showSuggestions(input);
  } else {
    console.log("Autocomplete is inactive");
    if (suggestionsDiv) {
      suggestionsDiv.style.display = 'none';
    }
  }
}

// Handle input events
document.addEventListener('input', function(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    currentInput = e.target;
    console.log("Input event triggered on:", currentInput.tagName, "with value:", currentInput.value);
    performAutocomplete(currentInput);
  }
});

// Handle clicking outside suggestions
document.addEventListener('click', function(e) {
  if (suggestionsDiv && !suggestionsDiv.contains(e.target) && e.target !== currentInput) {
    suggestionsDiv.style.display = 'none';
  }
});

// Handle focus events
document.addEventListener('focus', function(e) {
  if ((e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') && e.target.value) {
    currentInput = e.target;
    console.log("Focus event triggered on:", currentInput.tagName, "with value:", currentInput.value);
    performAutocomplete(currentInput);
  }
}, true);