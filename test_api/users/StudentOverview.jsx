import React from 'react';
import { format } from 'date-fns';
import { Box } from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { School, CheckCircle, Assignment, Grading, Star } from '@mui/icons-material';
import './StudentOverview.css';
import dummyData from './dummyData'; 

const StudentOverview = ({ student, metrics, activities, analytics }) => {

    console.log(student);
  const gradeData = [
    { name: 'Advanced ML', grade: 90 },
    { name: 'Web Dev', grade: 89.5 },
    { name: 'Data Structures', grade: 85 }
  ];

  return (
    <div className="student-overview-root">
      <div className="student-header-card">
        <div className="student-header-flex">
          <img className="student-avatar" src={student?.profile_picture} alt="profile" />
          <div className="student-header-info">
            <div className="student-welcome">Welcome back, <span>{student?.first_name}</span>!</div>
            <div className="student-email">{student?.email}</div>
            <div className="student-id">Student ID: <b>{student?.student_id || 'N/A'}</b></div>
            <div className="student-enrollment">Member since {format(new Date(student?.enrollmentDate), 'MMMM yyyy')}</div>
            <div className="student-points">
              <Star style={{ color: '#1976d2', fontSize: 20, verticalAlign: 'middle' }} />
              <span className="points-text">{student?.points} Points (Rank #{dummyData.gamification.leaderboardRank})</span>
            </div>
          </div>
        </div>
        <div className="student-metrics-grid">
          {[{
            label: 'Enrolled Courses', value: metrics.enrolledCourses, icon: <School style={{ color: '#1976d2', fontSize: 32 }} />
          }, {
            label: 'Completed', value: metrics.completedCourses, icon: <CheckCircle style={{ color: '#43a047', fontSize: 32 }} />
          }, {
            label: 'Assignments Due', value: metrics.assignmentsDue, icon: <Assignment style={{ color: '#ffa000', fontSize: 32 }} />
          }, {
            label: 'Average Grade', value: `${metrics.averageGrade}%`, icon: <Grading style={{ color: '#1976d2', fontSize: 32 }} />
          }].map((metric, idx) => (
            <div className="student-metric-card" key={idx}>
              <div className="metric-label-icon">
                <span className="metric-label">{metric.label}</span>
                {metric.icon}
              </div>
              <div className="metric-value">{metric.value}</div>
              {metric.label === 'Average Grade' && (
                <div className="metric-progress">
                  <div className="progress-bar" style={{ width: `${metrics.averageGrade}%` }} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="student-main-grid">
        <div className="student-grades-card">
          <div className="grades-title">Course Grades</div>
          <div className="grades-chart">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={gradeData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Bar dataKey="grade" fill="#1976d2" name="Your Grade" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="student-analytics-card">
          <div className="analytics-title">Learning Analytics</div>
          <div className="analytics-info">
            <div>Time Spent: <b>{analytics.timeSpent.total}</b> (Weekly: <b>{analytics.timeSpent.weekly}</b>)</div>
            <div>Strengths: <span>{analytics.strengths.join(', ')}</span></div>
            <div>Areas to Improve: <span>{analytics.weaknesses.join(', ')}</span></div>
            <button className="analytics-report-btn">View Detailed Report</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentOverview;