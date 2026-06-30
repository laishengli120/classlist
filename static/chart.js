(function () {
    const charts = window.classlistCharts || {};
    const baseFont = '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif';
    const colors = {
        accent: '#C96442',
        sage: '#5F7D68',
        blue: '#627789',
        muted: '#77746D',
        grid: '#ECE9E2',
        ink: '#2D2C28',
    };

    function axisOptions() {
        return {
            ticks: {
                color: colors.muted,
                font: { family: baseFont },
            },
            grid: {
                color: colors.grid,
                drawBorder: false,
            },
        };
    }

    function renderTrend() {
        const canvas = document.getElementById('trendChart');
        const data = charts.trend;
        if (!canvas || !window.Chart || !data || !data.labels || !data.labels.length) {
            return;
        }

        new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: '平均分',
                    data: data.values,
                    borderColor: colors.accent,
                    backgroundColor: colors.accent,
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    tension: 0.28,
                    spanGaps: true,
                    fill: false,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        titleFont: { family: baseFont },
                        bodyFont: { family: baseFont },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        suggestedMax: 100,
                        ...axisOptions(),
                    },
                    x: {
                        ...axisOptions(),
                        grid: { display: false },
                    },
                },
            },
        });
    }

    function renderDistribution() {
        const canvas = document.getElementById('distributionChart');
        const data = charts.distribution;
        if (!canvas || !window.Chart || !Array.isArray(data) || !data.length) {
            return;
        }

        new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.map((item) => item.label),
                datasets: [{
                    label: '人数',
                    data: data.map((item) => item.count),
                    backgroundColor: [colors.blue, colors.sage, '#8D8A80', '#B78A45', colors.accent],
                    borderRadius: 6,
                    borderSkipped: false,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        titleFont: { family: baseFont },
                        bodyFont: { family: baseFont },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0, color: colors.muted, font: { family: baseFont } },
                        grid: { color: colors.grid, drawBorder: false },
                    },
                    x: {
                        ticks: { color: colors.muted, font: { family: baseFont } },
                        grid: { display: false },
                    },
                },
            },
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        renderTrend();
        renderDistribution();
    });
}());
