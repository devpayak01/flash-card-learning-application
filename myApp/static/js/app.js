/* ===================================================================
   FlashMind — JavaScript
   ================================================================ */

// ---- Study Mode Logic ----

let currentCardIndex = 0;
let correctCount = 0;
let answeredCards = new Set();
let studyStartTime = Date.now();
let isFlipped = false;

function initStudy() {
    if (typeof CARDS_DATA === 'undefined' || !CARDS_DATA.length) return;
    showCard(0);
}

function showCard(index) {
    if (typeof CARDS_DATA === 'undefined') return;

    const card = CARDS_DATA[index];
    document.getElementById('cardQuestion').textContent = card.question;
    document.getElementById('cardAnswer').textContent = card.answer;

    // Reset flip
    const flashcard = document.getElementById('flashcard');
    flashcard.classList.remove('flipped');
    isFlipped = false;

    // Hide answer buttons
    document.getElementById('answerButtons').style.display = 'none';

    // Update counter
    document.getElementById('currentIndex').textContent = index + 1;

    // Update progress bar
    const progress = ((answeredCards.size) / CARDS_DATA.length) * 100;
    document.getElementById('studyProgress').style.width = progress + '%';

    // Update navigation
    document.getElementById('prevBtn').disabled = (index === 0);

    // Update correct count
    document.getElementById('correctCount').textContent = correctCount;

    // Add entrance animation
    const container = document.getElementById('flashcardContainer');
    container.classList.remove('animate-slide-up');
    void container.offsetWidth; // Force reflow
    container.classList.add('animate-slide-up');
}

function flipCard() {
    const flashcard = document.getElementById('flashcard');
    isFlipped = !isFlipped;

    if (isFlipped) {
        flashcard.classList.add('flipped');
        // Show answer buttons only if not already answered
        if (!answeredCards.has(currentCardIndex)) {
            document.getElementById('answerButtons').style.display = '';
        }
    } else {
        flashcard.classList.remove('flipped');
        document.getElementById('answerButtons').style.display = 'none';
    }
}

function answerCard(correct) {
    if (typeof CARDS_DATA === 'undefined') return;
    if (answeredCards.has(currentCardIndex)) return;

    answeredCards.add(currentCardIndex);

    if (correct) {
        correctCount++;
        document.getElementById('correctCount').textContent = correctCount;
    }

    // Send answer to server
    const card = CARDS_DATA[currentCardIndex];
    fetch('/api/study/answer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({
            card_id: card.id,
            correct: correct
        })
    }).catch(err => console.error('Error saving answer:', err));

    // Hide buttons
    document.getElementById('answerButtons').style.display = 'none';

    // Auto-advance after a short delay
    setTimeout(() => {
        if (currentCardIndex < CARDS_DATA.length - 1) {
            nextCard();
        } else {
            completeStudy();
        }
    }, 400);
}

function nextCard() {
    if (typeof CARDS_DATA === 'undefined') return;
    if (currentCardIndex < CARDS_DATA.length - 1) {
        currentCardIndex++;
        showCard(currentCardIndex);
    }
}

function prevCard() {
    if (currentCardIndex > 0) {
        currentCardIndex--;
        showCard(currentCardIndex);
    }
}

function skipCard() {
    if (typeof CARDS_DATA === 'undefined') return;
    if (currentCardIndex < CARDS_DATA.length - 1) {
        currentCardIndex++;
        showCard(currentCardIndex);
    } else {
        // Last card — check if all answered
        if (answeredCards.size >= CARDS_DATA.length) {
            completeStudy();
        } else {
            // Find first unanswered
            for (let i = 0; i < CARDS_DATA.length; i++) {
                if (!answeredCards.has(i)) {
                    currentCardIndex = i;
                    showCard(currentCardIndex);
                    return;
                }
            }
            completeStudy();
        }
    }
}

function completeStudy() {
    if (typeof CARDS_DATA === 'undefined') return;

    const duration = Math.round((Date.now() - studyStartTime) / 1000);
    const total = CARDS_DATA.length;
    const accuracy = total > 0 ? Math.round((correctCount / total) * 100) : 0;

    // Update modal
    document.getElementById('finalTotal').textContent = total;
    document.getElementById('finalCorrect').textContent = correctCount;
    document.getElementById('finalAccuracy').textContent = accuracy + '%';

    // Update progress to 100%
    document.getElementById('studyProgress').style.width = '100%';

    // Save session
    fetch('/api/study/complete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN
        },
        body: JSON.stringify({
            deck_id: DECK_ID,
            cards_studied: total,
            correct_count: correctCount,
            duration: duration
        })
    }).catch(err => console.error('Error saving session:', err));

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('completionModal'));
    modal.show();
}

function restartStudy() {
    currentCardIndex = 0;
    correctCount = 0;
    answeredCards.clear();
    studyStartTime = Date.now();

    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('completionModal'));
    if (modal) modal.hide();

    showCard(0);
}


// ---- Auto-dismiss flash messages ----
document.addEventListener('DOMContentLoaded', function () {
    // Initialize study mode if cards exist
    initStudy();

    // Auto-dismiss flash alerts after 5 seconds
    const alerts = document.querySelectorAll('.flash-alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });

    // Add stagger animation to list items
    document.querySelectorAll('.animate-stagger').forEach((el, i) => {
        el.style.animationDelay = (i * 0.05) + 's';
    });
});
