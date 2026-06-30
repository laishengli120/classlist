function createChart() {
    const pathArray = window.location.pathname.split('/');
    const studentId = pathArray[pathArray.length - 1];
    const palette = ['#2563eb', '#0f766e', '#c2410c', '#7c3aed', '#0e7490', '#be123c'];

    fetch(`/api/student/course/${studentId}`)
        .then(response => response.json())
        .then(courseIds => {
            if (!courseIds.length) {
                return;
            }

            return Promise.all(
                courseIds.map(courseId =>
                    fetch(`/course/${courseId}/${studentId}`).then(response => response.json())
                )
            );
        })
        .then(courseGroups => {
            if (!courseGroups) {
                return;
            }

            const allDates = new Set();
            courseGroups.forEach(group => {
                group.forEach(item => allDates.add(item.exam_date));
            });
            const labels = Array.from(allDates).sort();

            const datasets = courseGroups
                .filter(group => group.length)
                .map((group, index) => {
                    const color = palette[index % palette.length];
                    return {
                        label: group[0].course_name,
                        data: labels.map(date => {
                            const item = group.find(score => score.exam_date === date);
                            return item ? item.average_score : null;
                        }),
                        fill: false,
                        borderColor: color,
                        backgroundColor: color,
                        borderWidth: 2,
                        pointRadius: 3,
                        tension: 0.25,
                    };
                });

            if (!datasets.length) {
                return;
            }

            const ctx = document.getElementById('myChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: { labels, datasets },
                options: {
                    plugins: {
                        legend: {
                            labels: {
                                color: '#172033',
                                font: { family: 'Inter, Noto Sans SC, sans-serif' },
                            },
                        },
                    },
                    layout: {
                        padding: {
                            left: 10,
                            right: 10,
                            top: 10,
                            bottom: 10,
                        },
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { color: '#64748b' },
                            grid: {
                                color: '#e2e8f0',
                                lineWidth: 1,
                                drawBorder: false,
                            },
                        },
                        x: {
                            ticks: { color: '#64748b' },
                            grid: {
                                display: false,
                            },
                        },
                    },
                },
            });
        });
}
