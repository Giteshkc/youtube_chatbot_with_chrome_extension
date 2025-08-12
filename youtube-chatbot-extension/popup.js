// youtube-chatbot-extension/popup.js

document.addEventListener('DOMContentLoaded', function() {
    const videoIdInput = document.getElementById('videoId');
    const questionInput = document.getElementById('question');
    const askButton = document.getElementById('askButton');
    const responseDiv = document.getElementById('response');

    // Optional: Try to get video ID from the current tab URL
    chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
        let currentVideoId = "iv-5mZ_9CPY"; // Set a default example ID

        // Add checks here: if tabs exist, if it has at least one element, and if that element has a URL
        if (tabs && tabs.length > 0 && tabs[0].url) {
            const url = tabs[0].url;
            // More robust Regex to extract video ID from various YouTube URL formats
            const videoIdMatch = url.match(/(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/|y2u\.be\/)([a-zA-Z0-9_-]{11})/);

            if (videoIdMatch && videoIdMatch[1]) { // Use videoIdMatch[1] to get the captured video ID
                currentVideoId = videoIdMatch[1];
            }
        }
        videoIdInput.value = currentVideoId; // Set the input field's value
    });

    askButton.addEventListener('click', async function() {
        const videoId = videoIdInput.value.trim();
        const question = questionInput.value.trim();

        if (!videoId || !question) {
            responseDiv.textContent = 'Please enter both video ID and a question.';
            responseDiv.style.color = 'red';
            return;
        }

        responseDiv.textContent = 'Loading...';
        responseDiv.classList.add('loading');
        responseDiv.style.color = '#777';
        askButton.disabled = true;

        // Ensure this URL is correct for local testing
        const backendUrl = 'http://127.0.0.1:5000/ask_video';

        try {
            const response = await fetch(backendUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ videoId: videoId, question: question })
            });

            const data = await response.json();

            if (response.ok) {
                responseDiv.textContent = data.response;
                responseDiv.style.color = '#333';
            } else {
                responseDiv.textContent = `Error: ${data.error || 'Something went wrong on the server.'}`;
                responseDiv.style.color = 'red';
                console.error('Server error response:', data);
            }
        } catch (error) {
            console.error('Fetch error:', error);
            responseDiv.textContent = `Network error: Could not connect to the backend server. Make sure it's running and CORS is enabled. Details: ${error.message}`;
            responseDiv.style.color = 'red';
        } finally {
            responseDiv.classList.remove('loading');
            askButton.disabled = false;
        }
    });
});