const feedbackForm = document.getElementById('feedback-form');
const feedbackInput = document.getElementById('feedback');
const charRemaining = document.getElementById('char-remaining');
const categorySelect = document.getElementById('category');
const otherCategoryContainer = document.getElementById('other-category-container');
const otherCategoryInput = document.getElementById('other-category');
const submitBtn = feedbackForm.querySelector('.submit-btn');
const statusMsg = document.getElementById('status-msg');
const voiceBtn = document.querySelector('.voice-btn');
const locationInput = document.getElementById('location');
const languageSelect = document.getElementById('language');

let recognition;
let isRecording = false;

// Language mapping for Web Speech API
const languageMap = {
  'en': 'en-US',
  'hi': 'hi-IN',
  'kn': 'kn-IN',
  'ta': 'ta-IN',
  'te': 'te-IN',
  'bn': 'bn-IN',
  'gu': 'gu-IN',
  'ml': 'ml-IN',
  'mr': 'mr-IN',
  'pa': 'pa-IN',
  'or': 'or-IN',
  'as': 'as-IN'
};

// Automatically detect location on page load
document.addEventListener('DOMContentLoaded', () => {
  detectLocation();
  updateCharCount();
});

// Detect user's location using geolocation API
function detectLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        try {
          // Use OpenStreetMap's Nominatim API for reverse geocoding
          const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`
          );
          const data = await response.json();
          if (data && data.display_name) {
            locationInput.value = data.display_name;
          } else {
            locationInput.value = 'Location not found';
          }
        } catch (error) {
          console.error('Error fetching location:', error);
          locationInput.value = '';
        }
      },
      (error) => {
        console.error('Geolocation error:', error);
        locationInput.value = ''; // Fallback to manual input
      }
    );
  } else {
    console.error('Geolocation not supported by this browser.');
    locationInput.value = ''; // Fallback to manual input
  }
}

// Character count for feedback input
function updateCharCount() {
  const remaining = 500 - feedbackInput.value.length;
  charRemaining.textContent = `${remaining} characters remaining`;
}

feedbackInput.addEventListener('input', updateCharCount);

// Show/hide "Other Concerns" input based on category selection
categorySelect.addEventListener('change', () => {
  if (categorySelect.value === 'Other') {
    otherCategoryContainer.style.display = 'block';
    otherCategoryInput.setAttribute('required', 'true');
  } else {
    otherCategoryContainer.style.display = 'none';
    otherCategoryInput.removeAttribute('required');
  }
});

// Voice input functionality
function startListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  
  if (!SpeechRecognition) {
    alert('Speech Recognition API not supported in this browser.');
    return;
  }

  recognition = new SpeechRecognition();
  const selectedLanguage = languageSelect.value;
  recognition.lang = languageMap[selectedLanguage] || 'en-US';
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  if (isRecording) {
    recognition.stop();
    return;
  }

  voiceBtn.classList.add('recording');
  voiceBtn.innerHTML = '<i class="fas fa-microphone-slash"></i> Stop Recording';
  isRecording = true;

  recognition.start();

  recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map(result => result[0].transcript)
      .join('');
    feedbackInput.value = transcript;
    updateCharCount();
  };

  recognition.onspeechend = () => {
    recognition.stop();
    voiceBtn.classList.remove('recording');
    voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> Voice Input';
    isRecording = false;
  };

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    voiceBtn.classList.remove('recording');
    voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> Voice Input';
    isRecording = false;
    if (event.error === 'no-speech') {
      alert('No speech detected. Please try again.');
    } else if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      alert('Microphone access denied. Please allow microphone access to use voice input.');
    } else {
      alert('Error during speech recognition: ' + event.error);
    }
  };
}

// Form submission
feedbackForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const name = document.getElementById('name').value;
  const location = locationInput.value;
  const language = languageSelect.value;
  const category = categorySelect.value === 'Other' ? otherCategoryInput.value : categorySelect.value;
  const text = feedbackInput.value;

  const data = { name, location, language, category, text };

  submitBtn.classList.add('sending');
  submitBtn.innerHTML = '<i class="fas fa-spinner"></i> Sending...';
  statusMsg.textContent = 'Submitting your feedback...';
  statusMsg.classList.add('show', 'info');

  try {
    const response = await fetch('http://localhost:5000/api/v1/feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    const result = await response.json();

    if (response.ok) {
      submitBtn.classList.remove('sending');
      submitBtn.classList.add('success');
      submitBtn.innerHTML = '<i class="fas fa-check"></i> Submitted';
      statusMsg.textContent = 'Feedback submitted successfully!';
      statusMsg.classList.remove('info');
      statusMsg.classList.add('success');

      setTimeout(() => {
        showPopup('success');
        feedbackForm.reset();
        otherCategoryContainer.style.display = 'none';
        updateCharCount();
        submitBtn.classList.remove('success');
        submitBtn.innerHTML = 'Submit Feedback <i class="fas fa-paper-plane"></i>';
        statusMsg.classList.remove('show', 'success');
      }, 1000);
    } else {
      throw new Error(result.message || 'Failed to submit feedback');
    }
  } catch (error) {
    console.error('Error submitting feedback:', error);
    submitBtn.classList.remove('sending');
    submitBtn.innerHTML = 'Submit Feedback <i class="fas fa-paper-plane"></i>';
    statusMsg.textContent = 'Error submitting feedback. Please try again.';
    statusMsg.classList.remove('info');
    statusMsg.classList.add('error');

    setTimeout(() => {
      showPopup('error');
      statusMsg.classList.remove('show', 'error');
    }, 1000);
  }
});

// Popup handling
function showPopup(type) {
  const popup = document.getElementById(`${type}-popup`);
  popup.classList.add('visible');
}

function closePopup() {
  document.querySelectorAll('.popup-overlay').forEach(popup => {
    popup.classList.remove('visible');
  });
}