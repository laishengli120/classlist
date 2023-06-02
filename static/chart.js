function createChart() {
    let pathArray = window.location.pathname.split('/');
    let student_id = pathArray[pathArray.length - 1];  // 获取URL的最后一部分，即学生ID

    fetch(`/api/student/course/${student_id}`)
        .then(response => response.json())
        .then(course_ids => {
            let datasets = [];
            let all_dates = new Set();

            Promise.all(course_ids.map(course_id => fetch(`/course/${course_id}`)
                .then(response => response.json())
                .then(data => {
                    data.forEach(item => {
                        const date = item.exam_date;
                        all_dates.add(date);
                    });
                    return data;
                })))
                .then(courseDate => {
                    let all_dates_array = Array.from(all_dates).sort();
                    courseDate.forEach((data, index) => {
                        let course_name = data[0].course_name;
                        let scores = all_dates_array.map(date => {
                            const item = data.find(item => item.exam_date === date);
                            return item ? item.average_score : null;
                        });
                        datasets.push({
                            label: course_name,
                            data: scores,
                            fill: false,
                            // borderColor: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'][length % 8],
                            tension: 0.1
                        });
                    }); // end of courseDate.forEach
                    if (datasets.length === course_ids.length) {
                        const ctx = document.getElementById('myChart').getContext('2d');
                        ctx.fillStyle = 'yeallow';
                        ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
                        new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: all_dates_array,
                                datasets: datasets
                            },
                            options: {
                                layout: {
                                    padding: {
                                        left: 10,
                                        right: 10,
                                        top: 10,
                                        bottom: 10
                                    }
                                },
                                scales: {
                                    y: {
                                        grid: {
                            
                                            lineWidth: 1.5,
                                            drawBorder: false
                                        },
                                    },
                                    x: {
                                        grid: {
                                            display: false
                                        }
                                    }
                                }
                            }

                        });
                    }
                });
            });
        };