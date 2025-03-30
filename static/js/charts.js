// Chart.js implementation for admin dashboard metrics visualization

class AdminDashboardCharts {
    constructor(data) {
        this.data = data;
        this.charts = {};
        
        this.initializeCharts();
    }
    
    initializeCharts() {
        // Create line charts for various metrics
        this.createUserChart();
        this.createConsultationChart();
        this.createRevenueChart();
    }
    
    createUserChart() {
        const ctx = document.getElementById('users-chart');
        
        if (!ctx) return;
        
        this.charts.users = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.data.dates,
                datasets: [
                    {
                        label: 'New Patients',
                        data: this.data.new_patients,
                        borderColor: 'rgba(54, 162, 235, 1)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'New Doctors',
                        data: this.data.new_doctors,
                        borderColor: 'rgba(255, 99, 132, 1)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'New Users Registration Trend',
                        color: '#f8f9fa',
                        font: {
                            size: 16
                        }
                    },
                    legend: {
                        labels: {
                            color: '#f8f9fa'
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Date',
                            color: '#f8f9fa'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#f8f9fa'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Users',
                            color: '#f8f9fa'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#f8f9fa'
                        }
                    }
                }
            }
        });
    }
    
    createConsultationChart() {
        const ctx = document.getElementById('consultations-chart');
        
        if (!ctx) return;
        
        this.charts.consultations = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.data.dates,
                datasets: [
                    {
                        label: 'Completed Consultations',
                        data: this.data.consultations,
                        borderColor: 'rgba(75, 192, 192, 1)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Completed Consultations Trend',
                        color: '#f8f9fa',
                        font: {
                            size: 16
                        }
                    },
                    legend: {
                        labels: {
                            color: '#f8f9fa'
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Date',
                            color: '#f8f9fa'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#f8f9fa'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Consultations',
                            color: '#f8f9fa'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#f8f9fa'
                        }
                    }
                }
            }
        });
    }
    
    createRevenueChart() {
        const ctx = document.getElementById('revenue-chart');
        
        if (!ctx) return;
        
        this.charts.revenue = new Chart(ctx, {
            type: 'line',
            data: {
                labels: this.data.dates,
                datasets: [
                    {
                        label: 'Revenue ($)',
                        data: this.data.revenue,
                        borderColor: 'rgba(255, 206, 86, 1)',
                        backgroundColor: 'rgba(255, 206, 86, 0.2)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Revenue Trend',
                        color: '#f8f9fa',
                        font: {
                            size: 16
                        }
                    },
                    legend: {
                        labels: {
                            color: '#f8f9fa'
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += new Intl.NumberFormat('en-US', {
                                    style: 'currency',
                                    currency: 'USD'
                                }).format(context.parsed.y);
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Date',
                            color: '#f8f9fa'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#f8f9fa'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Revenue ($)',
                            color: '#f8f9fa'
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.1)'
                        },
                        ticks: {
                            color: '#f8f9fa',
                            callback: function(value) {
                                return '$' + value;
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Method to update chart data
    updateChartData(newData) {
        this.data = newData;
        
        // Update users chart
        if (this.charts.users) {
            this.charts.users.data.labels = newData.dates;
            this.charts.users.data.datasets[0].data = newData.new_patients;
            this.charts.users.data.datasets[1].data = newData.new_doctors;
            this.charts.users.update();
        }
        
        // Update consultations chart
        if (this.charts.consultations) {
            this.charts.consultations.data.labels = newData.dates;
            this.charts.consultations.data.datasets[0].data = newData.consultations;
            this.charts.consultations.update();
        }
        
        // Update revenue chart
        if (this.charts.revenue) {
            this.charts.revenue.data.labels = newData.dates;
            this.charts.revenue.data.datasets[0].data = newData.revenue;
            this.charts.revenue.update();
        }
    }
    
    // Method to create specialty pie chart
    createSpecialtyDistributionChart(specialties, counts) {
        const ctx = document.getElementById('specialty-distribution-chart');
        
        if (!ctx) return;
        
        // Define colors for each specialty
        const backgroundColors = [
            'rgba(255, 99, 132, 0.7)',
            'rgba(54, 162, 235, 0.7)',
            'rgba(255, 206, 86, 0.7)',
            'rgba(75, 192, 192, 0.7)',
            'rgba(153, 102, 255, 0.7)',
            'rgba(255, 159, 64, 0.7)',
            'rgba(199, 199, 199, 0.7)',
            'rgba(83, 102, 255, 0.7)',
            'rgba(40, 159, 64, 0.7)'
        ];
        
        this.charts.specialty = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: specialties,
                datasets: [
                    {
                        data: counts,
                        backgroundColor: backgroundColors,
                        borderColor: 'rgba(255, 255, 255, 0.7)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Doctor Specialty Distribution',
                        color: '#f8f9fa',
                        font: {
                            size: 16
                        }
                    },
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#f8f9fa',
                            padding: 10
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.formattedValue;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((context.raw / total) * 100);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
}

// Initialize admin dashboard charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    const adminMetricsContainer = document.getElementById('admin-metrics-container');
    
    if (adminMetricsContainer) {
        // Get chart data from data attributes
        const dates = JSON.parse(adminMetricsContainer.getAttribute('data-dates') || '[]');
        const newPatients = JSON.parse(adminMetricsContainer.getAttribute('data-new-patients') || '[]');
        const newDoctors = JSON.parse(adminMetricsContainer.getAttribute('data-new-doctors') || '[]');
        const consultations = JSON.parse(adminMetricsContainer.getAttribute('data-consultations') || '[]');
        const revenue = JSON.parse(adminMetricsContainer.getAttribute('data-revenue') || '[]');
        
        const chartData = {
            dates: dates,
            new_patients: newPatients,
            new_doctors: newDoctors,
            consultations: consultations,
            revenue: revenue
        };
        
        // Create admin dashboard charts
        const adminCharts = new AdminDashboardCharts(chartData);
        
        // Create specialty distribution chart if data is available
        const specialtyDistContainer = document.getElementById('specialty-distribution-container');
        if (specialtyDistContainer) {
            const specialties = JSON.parse(specialtyDistContainer.getAttribute('data-specialties') || '[]');
            const counts = JSON.parse(specialtyDistContainer.getAttribute('data-counts') || '[]');
            
            if (specialties.length > 0 && counts.length > 0) {
                adminCharts.createSpecialtyDistributionChart(specialties, counts);
            }
        }
        
        // Expose the admin charts object for debugging
        window.adminCharts = adminCharts;
    }
});
