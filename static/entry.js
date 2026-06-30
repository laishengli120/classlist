(function () {
    const config = window.entryConfig || {};
    const saveIndicator = document.getElementById('save-indicator');
    const progressBar = document.getElementById('entry-progress');
    const progressLabel = document.getElementById('progress-label');
    const enteredCount = document.getElementById('entered-count');
    const pendingCount = document.getElementById('pending-count');
    const helperName = document.getElementById('helper-name');
    const helperMeta = document.getElementById('helper-meta');
    const helperHistory = document.getElementById('helper-history');
    const helperStatus = document.getElementById('helper-status');
    const helperTip = document.getElementById('helper-tip');
    const timers = new Map();

    function rows() {
        return Array.from(document.querySelectorAll('.score-row'));
    }

    function scoreInputs() {
        return rows().map((row) => row.querySelector('.score-input'));
    }

    function saveUrl(studentId) {
        return config.saveUrlTemplate.replace(/0$/, String(studentId));
    }

    function setSaveState(text, state) {
        if (!saveIndicator) {
            return;
        }
        saveIndicator.textContent = text;
        saveIndicator.classList.remove('is-saving', 'is-error', 'is-saved');
        if (state) {
            saveIndicator.classList.add(state);
        }
    }

    function updateHelper(row) {
        if (!row || !helperName) {
            return;
        }
        rows().forEach((item) => item.classList.remove('is-active'));
        row.classList.add('is-active');

        const history = JSON.parse(row.dataset.history || '[]');
        const scores = history.map((item) => item.score).join(' · ');
        const changeText = row.querySelector('.change-cell').textContent.trim();
        helperName.textContent = row.dataset.studentName;
        helperMeta.textContent = row.dataset.studentNumber ? `学号 ${row.dataset.studentNumber}` : '未填写学号';
        helperHistory.textContent = scores || '暂无历史成绩';
        helperStatus.textContent = row.dataset.status || '未录入';
        if (changeText && changeText !== '—') {
            helperTip.textContent = changeText.startsWith('-')
                ? `本次较上次下降 ${changeText.replace('-', '')} 分，建议查看失分原因。`
                : `本次较上次提高 ${changeText.replace('+', '')} 分，近期状态向好。`;
        } else {
            helperTip.textContent = '录入后会根据最近成绩显示变化。';
        }
    }

    function applySaveResult(row, data) {
        row.dataset.status = data.status_label;
        row.querySelector('.score-input').value = data.display;
        row.querySelector('.grade-cell').textContent = data.grade;

        const changeCell = row.querySelector('.change-cell');
        changeCell.textContent = data.change_label;
        changeCell.classList.toggle('is-up', Number(data.change) > 0);
        changeCell.classList.toggle('is-down', Number(data.change) < 0);

        helperStatus.textContent = data.status_label;
        if (data.progress) {
            enteredCount.textContent = data.progress.entered;
            pendingCount.textContent = Math.max(data.progress.total - data.progress.entered, 0);
            progressLabel.textContent = `${data.progress.percent}%`;
            progressBar.style.setProperty('--progress', `${data.progress.percent}%`);
        }
        updateHelper(row);
    }

    function saveRow(row) {
        const studentId = row.dataset.studentId;
        const score = row.querySelector('.score-input').value;
        const remark = row.querySelector('.remark-input').value;
        setSaveState('正在保存…', 'is-saving');

        return fetch(saveUrl(studentId), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ score, remark }),
        })
            .then((response) => response.json().then((data) => ({ response, data })))
            .then(({ response, data }) => {
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || '保存失败');
                }
                applySaveResult(row, data);
                setSaveState('已保存', 'is-saved');
                window.setTimeout(() => setSaveState('已保存', ''), 1800);
            })
            .catch((error) => {
                setSaveState(error.message, 'is-error');
            });
    }

    function scheduleSave(row, delay) {
        const studentId = row.dataset.studentId;
        window.clearTimeout(timers.get(studentId));
        timers.set(studentId, window.setTimeout(() => saveRow(row), delay));
    }

    function focusInputAt(index) {
        const inputs = scoreInputs();
        const target = inputs[index];
        if (!target) {
            return;
        }
        target.focus();
        target.select();
        updateHelper(target.closest('.score-row'));
    }

    document.addEventListener('DOMContentLoaded', function () {
        rows().forEach((row, index) => {
            const scoreInput = row.querySelector('.score-input');
            const remarkInput = row.querySelector('.remark-input');
            const studentButton = row.querySelector('.student-cell');

            studentButton.addEventListener('click', function () {
                updateHelper(row);
                scoreInput.focus();
                scoreInput.select();
            });

            scoreInput.addEventListener('focus', function () {
                updateHelper(row);
                scoreInput.select();
            });

            scoreInput.addEventListener('input', function () {
                scheduleSave(row, 420);
            });

            scoreInput.addEventListener('blur', function () {
                scheduleSave(row, 0);
            });

            scoreInput.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    saveRow(row).then(() => focusInputAt(index + 1));
                }
                if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    focusInputAt(index + 1);
                }
                if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    focusInputAt(index - 1);
                }
            });

            remarkInput.addEventListener('focus', function () {
                updateHelper(row);
            });

            remarkInput.addEventListener('input', function () {
                scheduleSave(row, 520);
            });

            remarkInput.addEventListener('blur', function () {
                scheduleSave(row, 0);
            });
        });

        const firstRow = rows()[0];
        if (firstRow) {
            updateHelper(firstRow);
        }
    });
}());
