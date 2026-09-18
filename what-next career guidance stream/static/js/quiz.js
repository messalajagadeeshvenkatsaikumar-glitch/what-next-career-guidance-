document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("quizForm");
    const progressBar = document.getElementById("quizProgressBar");
    const answeredCountEl = document.getElementById("answeredCount");
    const previousButton = document.getElementById("previousQuestion");
    const nextButton = document.getElementById("nextQuestion");
    const submitButton = document.getElementById("submitQuiz");
    const stepEl = document.getElementById("quizStep");

    if (!form) return;

    const questionGroups = {};
    form.querySelectorAll("input[type=radio]").forEach(function (input) {
        if (!questionGroups[input.name]) {
            questionGroups[input.name] = [];
        }
        questionGroups[input.name].push(input);
    });

    const totalQuestions = Object.keys(questionGroups).length;
    const questionElements = Array.from(form.querySelectorAll(".quiz-question"));
    let currentIndex = 0;

    function currentQuestionAnswered() {
        const currentQuestion = questionElements[currentIndex];
        return currentQuestion ? Boolean(currentQuestion.querySelector("input[type=radio]:checked")) : false;
    }

    function showQuestion(index) {
        currentIndex = index;
        questionElements.forEach(function (question, questionIndex) {
            const active = questionIndex === currentIndex;
            question.hidden = !active;
            question.classList.toggle("is-active", active);
        });

        const isLast = currentIndex === questionElements.length - 1;
        if (previousButton) previousButton.disabled = currentIndex === 0;
        if (nextButton) nextButton.hidden = isLast;
        if (submitButton) submitButton.hidden = !isLast;
        if (stepEl) stepEl.textContent = "Question " + (currentIndex + 1) + " of " + totalQuestions;
    }

    function updateProgress() {
        let answered = 0;
        Object.keys(questionGroups).forEach(function (name) {
            const checked = questionGroups[name].some(function (input) {
                return input.checked;
            });
            if (checked) answered += 1;
        });

        const pct = totalQuestions ? (answered / totalQuestions) * 100 : 0;
        if (progressBar) progressBar.style.width = pct + "%";
        if (answeredCountEl) answeredCountEl.textContent = answered;
    }

    form.addEventListener("change", updateProgress);
    updateProgress();
    showQuestion(0);

    if (nextButton) {
        nextButton.addEventListener("click", function () {
            if (!currentQuestionAnswered()) {
                alert("Please answer this question before continuing.");
                return;
            }
            showQuestion(Math.min(currentIndex + 1, questionElements.length - 1));
        });
    }

    if (previousButton) {
        previousButton.addEventListener("click", function () {
            showQuestion(Math.max(currentIndex - 1, 0));
        });
    }

    form.addEventListener("submit", function (e) {
        let answered = 0;
        Object.keys(questionGroups).forEach(function (name) {
            const checked = questionGroups[name].some(function (input) {
                return input.checked;
            });
            if (checked) answered += 1;
        });

        if (currentIndex !== questionElements.length - 1 || answered < totalQuestions) {
            e.preventDefault();
            alert("Please answer all questions before submitting (" +
                  answered + " of " + totalQuestions + " answered).");
        }
    });
});
