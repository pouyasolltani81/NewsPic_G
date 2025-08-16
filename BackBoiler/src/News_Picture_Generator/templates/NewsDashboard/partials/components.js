
      // Modal elements
      const modal = document.getElementById('generateModal');
      const generateBtn = document.getElementById('generateBtn');
      const closeModal = document.getElementById('closeModal');
      const cancelBtn = document.getElementById('cancelBtn');
      const generateForm = document.getElementById('generateForm');
      const generateText = document.getElementById('generateText');
      const generateSpinner = document.getElementById('generateSpinner');
      
      // Filter functionality
      const imageFilter = document.getElementById('imageFilter');
      const imageCards = document.querySelectorAll('.image-card');
      
      // Show/hide modal
      generateBtn.addEventListener('click', () => {
          modal.classList.remove('hidden');
          modal.classList.add('flex');
      });
      
      closeModal.addEventListener('click', () => {
          modal.classList.add('hidden');
          modal.classList.remove('flex');
      });
      
      cancelBtn.addEventListener('click', () => {
          modal.classList.add('hidden');
          modal.classList.remove('flex');
      });
      
      // Close modal on outside click
      modal.addEventListener('click', (e) => {
          if (e.target === modal) {
              modal.classList.add('hidden');
              modal.classList.remove('flex');
          }
      });
      
      // Handle form submission
      generateForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          
          // Show loading state
          generateText.textContent = 'Generating...';
          generateSpinner.classList.remove('hidden');
          generateBtn.disabled = true;
          
          const formData = new FormData(generateForm);
          const data = {
              prompt: formData.get('prompt'),
              width: parseInt(formData.get('width')),
              height: parseInt(formData.get('height')),
              negative_prompt: formData.get('negative_prompt'),
              seed: parseInt(formData.get('seed')),
              steps: parseInt(formData.get('steps')),
              guidance_scale: parseFloat(formData.get('guidance_scale'))
          };
          
          try {
              const response = await fetch('/News_Picture_Generator/custom-images/generate/', {
                  method: 'POST',
                  headers: {
                      'Content-Type': 'application/json',
                      'X-CSRFToken': getCookie('csrftoken')
                  },
                  body: JSON.stringify(data)
              });
              
              if (response.ok) {
                  const result = await response.json();
                  // Show success message
                  alert('Image generated successfully!');
                  // Reload page to show new image
                  window.location.reload();
              } else {
                  throw new Error('Generation failed');
              }
          } catch (error) {
              alert('Error generating image. Please try again.');
              console.error('Error:', error);
          } finally {
              // Reset loading state
              generateText.textContent = 'Generate';
              generateSpinner.classList.add('hidden');
              generateBtn.disabled = false;
          }
      });
      
      // Filter functionality
      imageFilter.addEventListener('change', (e) => {
          const filterValue = e.target.value.toLowerCase();
          
          imageCards.forEach(card => {
              const title = card.dataset.title;
              const prompt = card.dataset.prompt;
              
              if (filterValue === 'all') {
                  card.style.display = '';
    
                } else if (filterValue === 'recent') {
                  // You'll need to add a data-date attribute to cards in the template
                  // For now, just show all
                  card.style.display = '';
              } else {
                  // Filter by keyword in title or prompt
                  if (title.includes(filterValue) || prompt.includes(filterValue)) {
                      card.style.display = '';
                  } else {
                      card.style.display = 'none';
                  }
              }
          });
      });
      
      // Helper function to get CSRF token
      function getCookie(name) {
          let cookieValue = null;
          if (document.cookie && document.cookie !== '') {
              const cookies = document.cookie.split(';');
              for (let i = 0; i < cookies.length; i++) {
                  const cookie = cookies[i].trim();
                  if (cookie.substring(0, name.length + 1) === (name + '=')) {
                      cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                      break;
                  }
              }
          }
          return cookieValue;
      }