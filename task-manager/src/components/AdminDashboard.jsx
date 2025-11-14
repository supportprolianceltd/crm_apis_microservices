 // components/AdminDashboard.jsx
 import React, { useState, useEffect } from 'react';
 import {
   Users,
   Shield,
   Settings,
   BarChart3,
   FileText,
   MessageSquare,
   AlertTriangle,
   Filter,
   Download,
   MoreVertical,
   LogOut,
   X,
   Calendar,
   Plus,
   Trash2,
   CheckCircle,
   AlertCircle,
   Upload,
   FileSpreadsheet
 } from 'lucide-react';
 import * as XLSX from 'xlsx';
import { taskAPI } from '../api/tasks';
import authAPI from '../api/auth';
import { StatCard, TaskStatusChart, RecentActivity } from './StatCard';
import Pagination from './Pagination';

const AdminDashboard = ({ user, onLogout }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [tasks, setTasks] = useState([]);
  const [users, setUsers] = useState([]);
  const [reports, setReports] = useState([]);
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalTasks: 0,
    totalUsers: 0,
    pendingReports: 0,
    recentComments: 0,
    overdueTasks: 0,
    highPriorityTasks: 0
  });
  const [userAnalytics, setUserAnalytics] = useState([]);

  // Confirmation modal state
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmConfig, setConfirmConfig] = useState({
    title: '',
    message: '',
    type: 'warning', // 'warning', 'danger', 'info'
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    onConfirm: () => {},
    onCancel: () => {}
  });

  useEffect(() => {
    loadAdminData();
  }, []);

  const loadAdminData = async () => {
    try {
      setLoading(true);

      // Load tasks and users first
      const [tasksRes, usersRes] = await Promise.all([
        taskAPI.getAllTasks(),
        authAPI.getUsers()
      ]);

      // Handle paginated responses
      const tasksData = tasksRes.data.results || tasksRes.data || [];
      const usersData = usersRes.data.results || [];

      console.log('Raw API responses:', {
        tasksResponse: tasksRes.data,
        usersResponse: usersRes.data,
        processedTasksCount: tasksData.length,
        processedUsersCount: usersData.length
      });

      setTasks(tasksData);
      setUsers(usersData);

      // Try to load reports and comments, but handle 403 errors gracefully
      try {
        const reportsRes = await taskAPI.getAllReports();
        setReports(reportsRes.data);
      } catch (error) {
        if (error.response?.status === 403) {
          console.warn('Reports not accessible to this user');
          setReports([]);
        } else {
          console.error('Error loading reports:', error);
          setReports([]);
        }
      }

      try {
        const commentsRes = await taskAPI.getAllComments();
        setComments(commentsRes.data);
      } catch (error) {
        if (error.response?.status === 403) {
          console.warn('Comments not accessible to this user');
          setComments([]);
        } else {
          console.error('Error loading comments:', error);
          setComments([]);
        }
      }

      console.log('Data loaded:', {
        tasksCount: tasksData.length,
        usersCount: usersData.length,
        tasksResponse: tasksRes.data,
        usersResponse: usersRes.data
      });

      calculateStats(tasksData, usersData, [], []);
      const analytics = calculateUserAnalytics(tasksData, usersData);
      setUserAnalytics(analytics);

      // Update state with processed data
      setTasks(tasksData);
      setUsers(usersData);
    } catch (error) {
      console.error('Error loading admin data:', error);
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (tasks, users, reports = [], comments = []) => {
    const today = new Date();
    const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

    setStats({
      totalTasks: tasks.length,
      totalUsers: users.length,
      pendingReports: reports.filter(r => !r.reviewed).length,
      recentComments: comments.filter(c => new Date(c.created_at) > lastWeek).length,
      overdueTasks: tasks.filter(t => new Date(t.due_date) < today && t.status !== 'completed').length,
      highPriorityTasks: tasks.filter(t => t.priority === 'high').length
    });
  };

  // Helper function to show confirmation modal
  const showConfirmation = (config) => {
    setConfirmConfig({
      title: config.title || 'Confirm Action',
      message: config.message || 'Are you sure you want to proceed?',
      type: config.type || 'warning',
      confirmText: config.confirmText || 'Confirm',
      cancelText: config.cancelText || 'Cancel',
      onConfirm: config.onConfirm || (() => {}),
      onCancel: config.onCancel || (() => setShowConfirmModal(false))
    });
    setShowConfirmModal(true);
  };

  const calculateUserAnalytics = (tasks, users) => {
    console.log('Calculating user analytics...');
    console.log('Tasks:', tasks.length, 'Users:', users.length);
    console.log('Sample task assigned_to_id:', tasks[0]?.assigned_to_id);
    console.log('Sample user id:', users[0]?.id);

    const userAnalytics = users.map(user => {
      const userTasks = tasks.filter(task => task.assigned_to_id === user.id);
      console.log(`User ${user.first_name} ${user.last_name} (${user.id}): ${userTasks.length} tasks`);

      const completedTasks = userTasks.filter(task => task.status === 'completed');
      const inProgressTasks = userTasks.filter(task => task.status === 'in_progress');
      const overdueTasks = userTasks.filter(task =>
        new Date(task.due_date) < new Date() && task.status !== 'completed'
      );

      const totalTasks = userTasks.length;
      const completionRate = totalTasks > 0 ? (completedTasks.length / totalTasks) * 100 : 0;
      const averageProgress = totalTasks > 0
        ? userTasks.reduce((sum, task) => sum + task.progress_percentage, 0) / totalTasks
        : 0;

      // Calculate performance score (weighted average)
      const performanceScore = (
        completionRate * 0.4 + // 40% weight on completion rate
        averageProgress * 0.4 + // 40% weight on average progress
        (totalTasks > 0 ? Math.max(0, 100 - (overdueTasks.length / totalTasks) * 100) : 100) * 0.2 // 20% weight on timeliness
      );

      return {
        user,
        totalTasks,
        completedTasks: completedTasks.length,
        inProgressTasks: inProgressTasks.length,
        overdueTasks: overdueTasks.length,
        completionRate: Math.round(completionRate),
        averageProgress: Math.round(averageProgress),
        performanceScore: Math.round(performanceScore),
        highPriorityTasks: userTasks.filter(task => task.priority === 'high').length,
        recentActivity: userTasks.filter(task =>
          new Date(task.updated_at) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
        ).length
      };
    });

    const sortedAnalytics = userAnalytics.sort((a, b) => b.performanceScore - a.performanceScore);
    console.log('User analytics calculated:', sortedAnalytics.map(a => ({
      name: `${a.user.first_name} ${a.user.last_name}`,
      tasks: a.totalTasks,
      score: a.performanceScore
    })));

    return sortedAnalytics;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-600 font-medium">Loading admin dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-xl border-b border-slate-200/60 sticky top-0 z-40 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-slate-900 to-slate-700 bg-clip-text text-transparent">Admin Dashboard</h1>
                <p className="text-xs text-slate-500">System Administration</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 rounded-lg border border-slate-200">
                <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {user.first_name[0]}{user.last_name[0]}
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{user.first_name} {user.last_name}</p>
                  <p className="text-xs text-slate-500">Administrator</p>
                </div>
              </div>

              <button
                onClick={onLogout}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-all duration-200 font-medium text-sm"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Navigation Tabs */}
        <div className="flex gap-1 bg-white rounded-2xl border border-slate-200 p-2 mb-6 shadow-sm">
          {[
            { key: 'overview', label: 'Overview', icon: BarChart3 },
            { key: 'tasks', label: 'Task Management', icon: FileText },
            { key: 'users', label: 'User Management', icon: Users },
            { key: 'analytics', label: 'User Analytics', icon: BarChart3 },
            { key: 'reports', label: 'Daily Reports', icon: FileText },
            { key: 'comments', label: 'Comments', icon: MessageSquare },
            { key: 'settings', label: 'Settings', icon: Settings }
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                activeTab === key
                  ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="space-y-6">
          {activeTab === 'overview' && <OverviewTab stats={stats} tasks={tasks} users={users} />}
          {activeTab === 'tasks' && <TaskManagementTab tasks={tasks} users={users} user={user} onUpdate={loadAdminData} onShowConfirm={showConfirmation} />}
          {activeTab === 'users' && <UserManagementTab users={users} onUpdate={loadAdminData} />}
          {activeTab === 'analytics' && <UserAnalyticsTab userAnalytics={userAnalytics} tasks={tasks} users={users} />}
          {activeTab === 'reports' && <ReportsManagementTab reports={reports} onUpdate={loadAdminData} />}
          {activeTab === 'comments' && <CommentsManagementTab comments={comments} onUpdate={loadAdminData} />}
          {activeTab === 'settings' && <SettingsTab />}
        </div>
      </div>
    </div>
  );
};

// Overview Tab Component
const OverviewTab = ({ stats, tasks, users }) => {
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        <StatCard
          title="Total Tasks"
          value={stats.totalTasks}
          icon={<FileText className="w-5 h-5" />}
          color="blue"
        />
        <StatCard
          title="Total Users"
          value={stats.totalUsers}
          icon={<Users className="w-5 h-5" />}
          color="green"
        />
        <StatCard
          title="Overdue Tasks"
          value={stats.overdueTasks}
          icon={<AlertTriangle className="w-5 h-5" />}
          color="red"
        />
        <StatCard
          title="High Priority"
          value={stats.highPriorityTasks}
          icon={<AlertTriangle className="w-5 h-5" />}
          color="orange"
        />
        <StatCard
          title="Pending Reports"
          value={stats.pendingReports}
          icon={<FileText className="w-5 h-5" />}
          color="purple"
        />
        <StatCard
          title="Recent Comments"
          value={stats.recentComments}
          icon={<MessageSquare className="w-5 h-5" />}
          color="indigo"
        />
      </div>

      {/* Charts and Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Task Status Distribution</h3>
          <TaskStatusChart tasks={tasks} />
        </div>
        
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Recent System Activity</h3>
          <RecentActivity tasks={tasks} />
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <button className="p-4 bg-blue-50 rounded-xl border border-blue-200 text-blue-700 hover:bg-blue-100 transition-colors">
            <Users className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm font-medium">Add User</span>
          </button>
          <button className="p-4 bg-green-50 rounded-xl border border-green-200 text-green-700 hover:bg-green-100 transition-colors">
            <FileText className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm font-medium">Create Task</span>
          </button>
          <button className="p-4 bg-orange-50 rounded-xl border border-orange-200 text-orange-700 hover:bg-orange-100 transition-colors">
            <Download className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm font-medium">Export Data</span>
          </button>
          <button className="p-4 bg-purple-50 rounded-xl border border-purple-200 text-purple-700 hover:bg-purple-100 transition-colors">
            <Settings className="w-6 h-6 mx-auto mb-2" />
            <span className="text-sm font-medium">System Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
};

// Task Management Tab Component
const TaskManagementTab = ({ tasks, users, user, onUpdate, onShowConfirm }) => {
  const [filter, setFilter] = useState('all');
  const [dateFilter, setDateFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTasks, setSelectedTasks] = useState([]);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showReassignModal, setShowReassignModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showBulkCreateModal, setShowBulkCreateModal] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [taskToEdit, setTaskToEdit] = useState(null);
  const [taskToReassign, setTaskToReassign] = useState(null);
  const [taskToView, setTaskToView] = useState(null);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [paginatedTasks, setPaginatedTasks] = useState([]);
  const [loading, setLoading] = useState(false);

  // Helper function to get date range for filtering
  const getDateRange = (dateFilterType) => {
    const today = new Date();
    const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const endOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59);

    switch (dateFilterType) {
      case 'today':
        return { start: startOfToday, end: endOfToday };
      case 'this_week': {
        const startOfWeek = new Date(today);
        startOfWeek.setDate(today.getDate() - today.getDay()); // Start of week (Sunday)
        startOfWeek.setHours(0, 0, 0, 0);
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);
        endOfWeek.setHours(23, 59, 59, 999);
        return { start: startOfWeek, end: endOfWeek };
      }
      case 'this_month': {
        const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0, 23, 59, 59, 999);
        return { start: startOfMonth, end: endOfMonth };
      }
      case 'overdue': {
        return { start: null, end: new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1, 23, 59, 59) };
      }
      case 'next_week': {
        const nextWeekStart = new Date(today);
        nextWeekStart.setDate(today.getDate() + (7 - today.getDay())); // Next Sunday
        const nextWeekEnd = new Date(nextWeekStart);
        nextWeekEnd.setDate(nextWeekStart.getDate() + 6);
        nextWeekEnd.setHours(23, 59, 59, 999);
        return { start: nextWeekStart, end: nextWeekEnd };
      }
      case 'next_month': {
        const nextMonthStart = new Date(today.getFullYear(), today.getMonth() + 1, 1);
        const nextMonthEnd = new Date(today.getFullYear(), today.getMonth() + 2, 0, 23, 59, 59, 999);
        return { start: nextMonthStart, end: nextMonthEnd };
      }
      default:
        return { start: null, end: null };
    }
  };

  // Load paginated tasks
  const loadTasks = async (page = 1, statusFilter = filter, dateFilterType = dateFilter, search = searchTerm) => {
    setLoading(true);
    try {
      const params = { page };

      // Only send status parameter for actual status values, not for 'all' or 'unassigned'
      if (statusFilter !== 'all' && statusFilter !== 'unassigned') {
        params.status = statusFilter;
      }

      if (search.trim()) {
        // Note: Backend might need to support search parameter
        params.search = search.trim();
      }

      const response = await taskAPI.getAllTasks(params);

      // Handle paginated response
      let tasksData = [];
      if (response.data.results) {
        tasksData = response.data.results;
        setTotalItems(response.data.count || 0);
        setTotalPages(Math.ceil((response.data.count || 0) / 20)); // Assuming page_size = 20
      } else {
        // Fallback for non-paginated response
        tasksData = response.data;
        setTotalItems(response.data.length);
        setTotalPages(1);
      }

      // Apply client-side filtering for status and assignment
      if (statusFilter === 'unassigned') {
        tasksData = tasksData.filter(task => !task.assigned_to_id || task.assigned_to_id === '');
      } else if (statusFilter !== 'all') {
        // Apply client-side status filtering as backup to backend filtering
        tasksData = tasksData.filter(task => task.status === statusFilter);
      }

      // Apply client-side date filtering
      if (dateFilterType !== 'all') {
        const dateRange = getDateRange(dateFilterType);
        tasksData = tasksData.filter(task => {
          if (!task.due_date) return false;

          const taskDueDate = new Date(task.due_date);

          if (dateFilterType === 'overdue') {
            return taskDueDate < dateRange.end && task.status !== 'completed';
          } else {
            return taskDueDate >= dateRange.start && taskDueDate <= dateRange.end;
          }
        });
      }

      setPaginatedTasks(tasksData);
      setCurrentPage(page);
    } catch (error) {
      console.error('Error loading tasks:', error);
      setPaginatedTasks([]);
      setTotalItems(0);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  };

  // Load tasks on mount and when filters change
  useEffect(() => {
    loadTasks(1, filter, dateFilter, searchTerm);
  }, [filter, dateFilter, searchTerm]);

  const handlePageChange = (page) => {
    loadTasks(page, filter, dateFilter, searchTerm);
  };

  const handleFilterChange = (newFilter) => {
    setFilter(newFilter);
    setCurrentPage(1);
  };

  const handleDateFilterChange = (newDateFilter) => {
    setDateFilter(newDateFilter);
    setCurrentPage(1);
  };

  const handleSearchChange = (newSearch) => {
    setSearchTerm(newSearch);
    setCurrentPage(1);
  };

  const handleBulkAction = async (action) => {
    // Implement bulk actions like delete, reassign, etc.
    console.log('Bulk action:', action, selectedTasks);
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Task Management</h2>
            <p className="text-sm text-slate-500">Manage all tasks in the system</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg transition-all font-medium"
            >
              Create Task
            </button>
            <button
              onClick={() => setShowBulkCreateModal(true)}
              className="px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:shadow-lg transition-all font-medium"
            >
              Bulk Create Tasks
            </button>
            <button className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-all font-medium">
              Export
            </button>
          </div>
        </div>

        {/* Filters and Search */}
        <div className="flex flex-col gap-4">
          {/* Status Filters */}
          <div className="flex gap-2 overflow-x-auto">
            {[
              { key: 'all', label: 'All Tasks' },
              { key: 'unassigned', label: 'Unassigned' },
              { key: 'not_started', label: 'Not Started' },
              { key: 'in_progress', label: 'In Progress' },
              { key: 'completed', label: 'Completed' },
              { key: 'blocked', label: 'Blocked' }
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => handleFilterChange(key)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize whitespace-nowrap ${
                  filter === key
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Date Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex gap-2 overflow-x-auto">
              <span className="text-sm font-medium text-slate-700 self-center mr-2">Due Date:</span>
              {[
                { key: 'all', label: 'All Dates' },
                { key: 'overdue', label: 'Overdue' },
                { key: 'today', label: 'Today' },
                { key: 'this_week', label: 'This Week' },
                { key: 'this_month', label: 'This Month' },
                { key: 'next_week', label: 'Next Week' },
                { key: 'next_month', label: 'Next Month' }
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => handleDateFilterChange(key)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap ${
                    dateFilter === key
                      ? 'bg-green-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="relative flex-1 max-w-md">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search tasks..."
                className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={searchTerm}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Tasks Table */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
              <p className="text-slate-600">Loading tasks...</p>
            </div>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">
                  <input type="checkbox" className="rounded border-slate-300" />
                </th>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Task</th>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Assigned To</th>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Priority</th>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Due Date</th>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Progress</th>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {paginatedTasks.length > 0 ? paginatedTasks.map(task => (
                <TaskTableRow
                  key={task.id}
                  task={task}
                  users={users}
                  onUpdate={() => loadTasks(currentPage, filter, searchTerm)}
                  onView={(task) => {
                    setTaskToView(task);
                    setShowDetailsModal(true);
                  }}
                  onEdit={(task) => {
                    setTaskToEdit(task);
                    setShowEditModal(true);
                  }}
                  onReassign={(task) => {
                    setTaskToReassign(task);
                    setShowReassignModal(true);
                  }}
                  onSelect={(selected) => {
                    if (selected) {
                      setSelectedTasks(prev => [...prev, task.id]);
                    } else {
                      setSelectedTasks(prev => prev.filter(id => id !== task.id));
                    }
                  }}
                  onShowConfirm={onShowConfirm}
                />
              )) : (
                <tr>
                  <td colSpan="8" className="px-6 py-12 text-center text-slate-500">
                    No tasks found matching your criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          totalItems={totalItems}
          pageSize={20}
          onPageChange={handlePageChange}
        />
      )}

      {/* Modals */}
      {showEditModal && taskToEdit && (
        <EditTaskModal
          task={taskToEdit}
          users={users}
          user={user}
          onClose={() => {
            setShowEditModal(false);
            setTaskToEdit(null);
          }}
          onTaskUpdated={onUpdate}
        />
      )}

      {showReassignModal && taskToReassign && (
        <ReassignTaskModal
          task={taskToReassign}
          users={users}
          onClose={() => {
            setShowReassignModal(false);
            setTaskToReassign(null);
          }}
          onTaskUpdated={onUpdate}
        />
      )}

      {showCreateModal && (
        <CreateTaskModal
          onClose={() => setShowCreateModal(false)}
          onTaskCreated={() => {
            setShowCreateModal(false);
            onUpdate();
          }}
        />
      )}

      {showBulkCreateModal && (
        <BulkCreateTasksModal
          onClose={() => {
            setShowBulkCreateModal(false);
            // Reset will be handled in the modal's useEffect
          }}
          onTasksCreated={() => {
            setShowBulkCreateModal(false);
            onUpdate();
          }}
        />
      )}

      {showDetailsModal && taskToView && (
        <TaskDetailsModal
          task={taskToView}
          users={users}
          onClose={() => {
            setShowDetailsModal(false);
            setTaskToView(null);
          }}
        />
      )}

    </div>
  );
};

// Task Table Row Component
const TaskTableRow = ({ task, users, onUpdate, onEdit, onReassign, onView, onSelect, onShowConfirm }) => {
  const [showActions, setShowActions] = useState(false);

  const statusConfig = {
    not_started: { color: 'text-slate-700', bg: 'bg-slate-100', label: 'Not Started' },
    in_progress: { color: 'text-blue-700', bg: 'bg-blue-100', label: 'In Progress' },
    completed: { color: 'text-green-700', bg: 'bg-green-100', label: 'Completed' },
    blocked: { color: 'text-amber-700', bg: 'bg-amber-100', label: 'Blocked' }
  };

  const priorityConfig = {
    low: { color: 'text-emerald-700', bg: 'bg-emerald-100', label: 'Low' },
    medium: { color: 'text-amber-700', bg: 'bg-amber-100', label: 'Medium' },
    high: { color: 'text-rose-700', bg: 'bg-rose-100', label: 'High' }
  };

  const handleDelete = () => {
    onShowConfirm({
      title: 'Delete Task',
      message: `Are you sure you want to delete the task "${task.title}"? This action cannot be undone.`,
      type: 'danger',
      confirmText: 'Delete Task',
      cancelText: 'Cancel',
      onConfirm: async () => {
        try {
          await taskAPI.deleteTask(task.id);
          onUpdate();
        } catch (error) {
          console.error('Error deleting task:', error);
        }
      }
    });
  };

  return (
    <tr className="hover:bg-slate-50 transition-colors">
      <td className="px-6 py-4">
        <input 
          type="checkbox" 
          className="rounded border-slate-300"
          onChange={(e) => onSelect(e.target.checked)}
        />
      </td>
      <td className="px-6 py-4">
        <div>
          <div className="font-medium text-slate-900">{task.title}</div>
          <div className="text-sm text-slate-500 line-clamp-1">{task.description}</div>
        </div>
      </td>
      <td className="px-6 py-4">
        {task.assigned_to_id ? (
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
              {task.assigned_to_first_name[0]}{task.assigned_to_last_name[0]}
            </div>
            <span className="text-sm text-slate-900">
              {task.assigned_to_first_name} {task.assigned_to_last_name}
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-gradient-to-br from-slate-400 to-slate-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
              <Users className="w-3 h-3" />
            </div>
            <span className="text-sm text-slate-500 italic">Unassigned</span>
          </div>
        )}
      </td>
      <td className="px-6 py-4">
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusConfig[task.status].bg} ${statusConfig[task.status].color}`}>
          {statusConfig[task.status].label}
        </span>
      </td>
      <td className="px-6 py-4">
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${priorityConfig[task.priority].bg} ${priorityConfig[task.priority].color}`}>
          {priorityConfig[task.priority].label}
        </span>
      </td>
      <td className="px-6 py-4 text-sm text-slate-900">
        {task.due_date ? new Date(task.due_date).toLocaleDateString() : 'No due date'}
      </td>
      <td className="px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"
              style={{ width: `${task.progress_percentage}%` }}
            />
          </div>
          <span className="text-xs font-medium text-slate-700 w-8">{task.progress_percentage}%</span>
        </div>
      </td>
      <td className="px-6 py-4">
        <div className="relative">
          <button
            onClick={() => setShowActions(!showActions)}
            className="p-1 hover:bg-slate-200 rounded-lg transition-colors"
          >
            <MoreVertical className="w-4 h-4 text-slate-600" />
          </button>
          
          {showActions && (
            <div className="absolute right-0 top-8 bg-white border border-slate-200 rounded-lg shadow-lg z-10 min-w-32">
              <button
                onClick={() => {
                  onView(task);
                  setShowActions(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              >
                View Details
              </button>
              <button
                onClick={() => {
                  onEdit(task);
                  setShowActions(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              >
                Edit
              </button>
              <button
                onClick={() => {
                  onReassign(task);
                  setShowActions(false);
                }}
                className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              >
                Reassign
              </button>
              <button
                onClick={handleDelete}
                className="w-full px-4 py-2 text-left text-sm text-rose-700 hover:bg-rose-50"
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
};

// Edit Task Modal Component
const EditTaskModal = ({ task, users, user, onClose, onTaskUpdated }) => {
  const [formData, setFormData] = useState({
    title: task.title || '',
    description: task.description || '',
    assigned_to_id: task.assigned_to_id || '',
    assigned_by_id: user.id,
    start_date: task.start_date ? task.start_date.split('T')[0] : '',
    due_date: task.due_date ? task.due_date.split('T')[0] : '',
    priority: task.priority || 'medium',
    status: task.status || 'not_started',
    progress_percentage: task.progress_percentage || 0
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await taskAPI.updateTask(task.id, formData);
      onTaskUpdated();
      onClose();
    } catch (error) {
      console.error('Error updating task:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Edit Task</h2>
              <p className="text-sm text-slate-500 mt-1">Update task details</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Task Title *</label>
            <input
              type="text"
              name="title"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.title}
              onChange={handleChange}
              placeholder="Enter task title..."
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Description</label>
            <textarea
              name="description"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.description}
              onChange={handleChange}
              placeholder="Describe the task..."
              rows="3"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Assign To User *</label>
            <select
              name="assigned_to_id"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.assigned_to_id}
              onChange={handleChange}
              required
            >
              <option value="">Select a user...</option>
              {users.map(user => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} ({user.email})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Start Date</label>
              <input
                type="date"
                name="start_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.start_date}
                onChange={handleChange}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Due Date</label>
              <input
                type="date"
                name="due_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.due_date}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Priority</label>
              <select
                name="priority"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.priority}
                onChange={handleChange}
              >
                <option value="low">Low Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="high">High Priority</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Status</label>
              <select
                name="status"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.status}
                onChange={handleChange}
              >
                <option value="not_started">Not Started</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="blocked">Blocked</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Progress Percentage</label>
            <input
              type="number"
              name="progress_percentage"
              min="0"
              max="100"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.progress_percentage}
              onChange={handleChange}
              placeholder="Enter progress percentage (0-100)"
            />
            <p className="text-xs text-slate-500 mt-1">Enter a value between 0 and 100</p>
          </div>
        </form>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
            {loading ? 'Updating...' : 'Update Task'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Reassign Task Modal Component
const ReassignTaskModal = ({ task, users, onClose, onTaskUpdated }) => {
  const [selectedUserId, setSelectedUserId] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedUserId) return;

    setLoading(true);

    try {
      // Get the selected user details
      const selectedUser = users.find(user => user.id == selectedUserId);

      // Send all required fields for the update
      const updateData = {
        title: task.title, // Required field
        assigned_to_id: selectedUserId,
        assigned_to_username: selectedUser?.username || '',
        assigned_to_first_name: selectedUser?.first_name || '',
        assigned_to_last_name: selectedUser?.last_name || '',
        assigned_to_email: selectedUser?.email || '',
        assigned_to_role: selectedUser?.role || '',
        assigned_to_job_role: selectedUser?.job_role || '',
        assigned_to_tenant: selectedUser?.tenant || '',
        assigned_to_branch: selectedUser?.branch || '',
        assigned_to_status: selectedUser?.status || '',
        assigned_to_permission_levels: selectedUser?.permission_levels || [],
        assigned_by_id: task.assigned_by_id, // Required field
        assigned_by_first_name: task.assigned_by_first_name,
        assigned_by_last_name: task.assigned_by_last_name,
        assigned_by_email: task.assigned_by_email,
        description: task.description,
        start_date: task.start_date,
        due_date: task.due_date,
        priority: task.priority,
        status: task.status,
        progress_percentage: task.progress_percentage
      };

      await taskAPI.updateTask(task.id, updateData);
      onTaskUpdated();
      onClose();
    } catch (error) {
      console.error('Error reassigning task:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Reassign Task</h2>
              <p className="text-sm text-slate-500 mt-1">Assign task to a different user</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
            <h3 className="text-sm font-semibold text-blue-900 mb-2">Current Task</h3>
            <p className="text-sm text-blue-800 font-medium">{task.title}</p>
            <p className="text-xs text-blue-600 mt-1">
              Currently assigned to: {task.assigned_to_first_name} {task.assigned_to_last_name}
            </p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Assign To New User *</label>
            <select
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              required
            >
              <option value="">Select a user...</option>
              {users.filter(user => user.id !== task.assigned_to_id).map(user => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} ({user.email})
                </option>
              ))}
            </select>
          </div>
        </form>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading || !selectedUserId}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
            {loading ? 'Reassigning...' : 'Reassign Task'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Create Task Modal Component
const CreateTaskModal = ({ onClose, onTaskCreated }) => {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    assigned_to_id: '',
    start_date: '',
    due_date: '',
    priority: 'medium',
    status: 'not_started'
  });
  const [loading, setLoading] = useState(false);
  const [calculatedDays, setCalculatedDays] = useState(null);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await authAPI.getUsers();
        setUsers(response.data.results || []);
      } catch (error) {
        console.error('Error fetching users:', error);
      } finally {
        setUsersLoading(false);
      }
    };

    fetchUsers();
  }, []);

  // Reset modal state when opened
  useEffect(() => {
    resetModal();
  }, []);

  const calculateDays = (startDate, endDate) => {
    if (!startDate || !endDate) {
      setCalculatedDays(null);
      return;
    }

    const start = new Date(startDate);
    const end = new Date(endDate);
    const diffTime = end - start;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays >= 0) {
      setCalculatedDays(diffDays);
    } else {
      setCalculatedDays(null);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });

    // Recalculate days when dates change
    if (name === 'start_date' || name === 'due_date') {
      const newStartDate = name === 'start_date' ? value : formData.start_date;
      const newEndDate = name === 'due_date' ? value : formData.due_date;
      calculateDays(newStartDate, newEndDate);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await taskAPI.createTask(formData);
      onTaskCreated();
    } catch (error) {
      console.error('Error creating task:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Create New Task</h2>
              <p className="text-sm text-slate-500 mt-1">Add a new task to the project</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Task Title *</label>
            <input
              type="text"
              name="title"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.title}
              onChange={handleChange}
              placeholder="Enter task title..."
              required
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Description</label>
            <textarea
              name="description"
              className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              value={formData.description}
              onChange={handleChange}
              placeholder="Describe the task..."
              rows="3"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-900 mb-2">Assign To User (Optional)</label>
            <select
              name="assigned_to_id"
              className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={formData.assigned_to_id}
              onChange={handleChange}
              disabled={usersLoading}
            >
              <option value="">
                {usersLoading ? 'Loading users...' : 'Leave unassigned (optional)'}
              </option>
              {users.map(user => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} ({user.email}) - {user.role}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">Select a user to assign this task, or leave unassigned</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Start Date</label>
              <input
                type="date"
                name="start_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.start_date}
                onChange={handleChange}
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Due Date</label>
              <input
                type="date"
                name="due_date"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.due_date}
                onChange={handleChange}
              />
            </div>
          </div>

          {calculatedDays !== null && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-900">
                  Task Duration: {calculatedDays} day{calculatedDays !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Priority</label>
              <select
                name="priority"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.priority}
                onChange={handleChange}
              >
                <option value="low">Low Priority</option>
                <option value="medium">Medium Priority</option>
                <option value="high">High Priority</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-900 mb-2">Status</label>
              <select
                name="status"
                className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={formData.status}
                onChange={handleChange}
              >
                <option value="not_started">Not Started</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="blocked">Blocked</option>
              </select>
            </div>
          </div>
        </form>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
            {loading ? 'Creating...' : 'Create Task'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium"
          >
            Cancel
          </button>
        </div>
      </div>

    </div>
  );
};

// Task Details Modal Component
const TaskDetailsModal = ({ task, users, onClose }) => {
  if (!task) return null;

  const statusConfig = {
    not_started: { color: 'text-slate-700', bg: 'bg-slate-100', label: 'Not Started' },
    in_progress: { color: 'text-blue-700', bg: 'bg-blue-100', label: 'In Progress' },
    completed: { color: 'text-green-700', bg: 'bg-green-100', label: 'Completed' },
    blocked: { color: 'text-amber-700', bg: 'bg-amber-100', label: 'Blocked' }
  };

  const priorityConfig = {
    low: { color: 'text-emerald-700', bg: 'bg-emerald-100', label: 'Low' },
    medium: { color: 'text-amber-700', bg: 'bg-amber-100', label: 'Medium' },
    high: { color: 'text-rose-700', bg: 'bg-rose-100', label: 'High' }
  };

  const assignedUser = users.find(user => user.id === task.assigned_to_id);

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <FileText className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-slate-900">{task.title}</h2>
                <p className="text-sm text-slate-500 mt-1">Task Details</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main Content */}
            <div className="lg:col-span-2 space-y-6">
              {/* Description */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Description</h3>
                <p className="text-slate-700 leading-relaxed">
                  {task.description || 'No description provided.'}
                </p>
              </div>

              {/* Progress */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Progress</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Completion</span>
                    <span className="text-sm font-semibold text-slate-900">{task.progress_percentage}%</span>
                  </div>
                  <div className="w-full h-3 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-300"
                      style={{ width: `${task.progress_percentage}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Additional Details */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Additional Information</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">Created By</label>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 bg-gradient-to-br from-purple-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                        {task.assigned_by_first_name ? task.assigned_by_first_name[0] : '?'}
                      </div>
                      <span className="text-sm text-slate-900">
                        {task.assigned_by_first_name} {task.assigned_by_last_name}
                      </span>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">Created Date</label>
                    <span className="text-sm text-slate-900">
                      {task.created_at ? new Date(task.created_at).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                      }) : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">Last Updated</label>
                    <span className="text-sm text-slate-900">
                      {task.updated_at ? new Date(task.updated_at).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                      }) : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">Task ID</label>
                    <span className="text-sm text-slate-900 font-mono">#{task.id}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Status & Priority */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Status & Priority</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-2">Status</label>
                    <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${statusConfig[task.status].bg} ${statusConfig[task.status].color}`}>
                      {statusConfig[task.status].label}
                    </span>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-2">Priority</label>
                    <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${priorityConfig[task.priority].bg} ${priorityConfig[task.priority].color}`}>
                      {priorityConfig[task.priority].label}
                    </span>
                  </div>
                </div>
              </div>

              {/* Assigned User */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Assigned To</h3>
                {task.assigned_to_id ? (
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white font-medium">
                      {task.assigned_to_first_name[0]}{task.assigned_to_last_name[0]}
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">
                        {task.assigned_to_first_name} {task.assigned_to_last_name}
                      </div>
                      <div className="text-sm text-slate-500">{task.assigned_to_email}</div>
                      <div className="text-xs text-slate-400 mt-1">{task.assigned_to_role || 'User'}</div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-slate-400 to-slate-500 rounded-full flex items-center justify-center text-white font-medium">
                      <Users className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-500 italic">Unassigned</div>
                      <div className="text-sm text-slate-400">This task has not been assigned to any user yet</div>
                    </div>
                  </div>
                )}
              </div>

              {/* Dates */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Timeline</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">Start Date</label>
                    <span className="text-sm text-slate-900">
                      {task.start_date ? new Date(task.start_date).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      }) : 'Not set'}
                    </span>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-500 mb-1">Due Date</label>
                    <span className={`text-sm ${new Date(task.due_date) < new Date() && task.status !== 'completed' ? 'text-red-600 font-medium' : 'text-slate-900'}`}>
                      {task.due_date ? new Date(task.due_date).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      }) : 'No due date'}
                    </span>
                  </div>
                  {task.due_date && (
                    <div>
                      <label className="block text-sm font-medium text-slate-500 mb-1">Days Remaining</label>
                      <span className={`text-sm font-medium ${Math.ceil((new Date(task.due_date) - new Date()) / (1000 * 60 * 60 * 24)) < 0 ? 'text-red-600' : 'text-slate-900'}`}>
                        {Math.ceil((new Date(task.due_date) - new Date()) / (1000 * 60 * 60 * 24))} days
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-3 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-all font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

// User Analytics Tab Component
// Displays user performance analytics and task assignments
// Uses getTasksByUser API to fetch individual user tasks for detailed view
const UserAnalyticsTab = ({ userAnalytics, tasks, users }) => {
  console.log('UserAnalyticsTab render:', {
    userAnalyticsCount: userAnalytics.length,
    tasksCount: tasks.length,
    usersCount: users.length,
    sampleUserAnalytics: userAnalytics[0],
    sampleTask: tasks[0]
  });
  const [selectedUser, setSelectedUser] = useState(null);
  const [userTasks, setUserTasks] = useState([]);

  const handleViewUserTasks = async (user) => {
    try {
      console.log('Fetching tasks for user:', user.id, user.first_name, user.last_name);
      // API Call: GET /api/project-manager/api/tasks/?assigned_to_id={userId}
      // As documented in POSTMAN_EXAMPLES.md - "Get Tasks by User (Analytics)"
      const response = await taskAPI.getTasksByUser(user.id);
      console.log('API Response:', response);

      // Handle paginated response structure
      const tasks = response.data.results || response.data || [];
      console.log('User tasks loaded:', tasks.length, 'tasks');

      setUserTasks(tasks);
      setSelectedUser(user);
    } catch (error) {
      console.error('Error fetching user tasks:', error);
      // Show error state
      setUserTasks([]);
      setSelectedUser(user);
    }
  };

  const getPerformanceColor = (score) => {
    if (score >= 80) return 'text-green-600 bg-green-100';
    if (score >= 60) return 'text-blue-600 bg-blue-100';
    if (score >= 40) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  return (
    <div className="space-y-6">
      {/* Analytics Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Active Users</p>
              <p className="text-2xl font-bold text-slate-900">{userAnalytics.length}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Avg Tasks/User</p>
              <p className="text-2xl font-bold text-slate-900">
                {(() => {
                  const avgTasks = userAnalytics.length > 0 ? Math.round(tasks.length / userAnalytics.length) : 0;
                  console.log('Avg Tasks/User calculation:', {
                    totalTasks: tasks.length,
                    totalUsers: userAnalytics.length,
                    avgTasks
                  });
                  return avgTasks;
                })()}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Avg Performance</p>
              <p className="text-2xl font-bold text-slate-900">
                {userAnalytics.length > 0
                  ? Math.round(userAnalytics.reduce((sum, user) => sum + user.performanceScore, 0) / userAnalytics.length)
                  : 0}%
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <p className="text-sm text-slate-500">Overdue Tasks</p>
              <p className="text-2xl font-bold text-slate-900">
                {userAnalytics.reduce((sum, user) => sum + user.overdueTasks, 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* User Performance Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <h2 className="text-xl font-bold text-slate-900">User Performance Analytics</h2>
          <p className="text-sm text-slate-500 mt-1">Performance metrics and task completion rates</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">User</th>
                <th className="px-6 py-3 text-center text-xs font-bold text-slate-900 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {userAnalytics.map(analytics => (
                <tr key={analytics.user.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                        {analytics.user.first_name[0]}{analytics.user.last_name[0]}
                      </div>
                      <div>
                        <div className="font-medium text-slate-900">
                          {analytics.user.first_name} {analytics.user.last_name}
                        </div>
                        <div className="text-sm text-slate-500">{analytics.user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <button
                      onClick={() => handleViewUserTasks(analytics.user)}
                      className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      View Analytics & Tasks
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* User Tasks Modal */}
      {selectedUser && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setSelectedUser(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                    <Users className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-slate-900">
                      {selectedUser.first_name} {selectedUser.last_name}'s Tasks
                    </h2>
                    <p className="text-sm text-slate-500 mt-1">Task assignments and progress ({userTasks.length} tasks)</p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedUser(null)}
                  className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
              {/* Analytics Summary Section */}
              <div className="mb-8">
                <h3 className="text-xl font-bold text-slate-900 mb-6">Performance Analytics</h3>
                {(() => {
                  // Calculate analytics from actual userTasks data
                  const totalTasks = userTasks.length;
                  const completedTasks = userTasks.filter(task => task.status === 'completed').length;
                  const inProgressTasks = userTasks.filter(task => task.status === 'in_progress').length;
                  const notStartedTasks = totalTasks - completedTasks - inProgressTasks;

                  const completionRate = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;
                  const averageProgress = totalTasks > 0
                    ? Math.round(userTasks.reduce((sum, task) => sum + task.progress_percentage, 0) / totalTasks)
                    : 0;

                  const overdueTasks = userTasks.filter(task =>
                    new Date(task.due_date) < new Date() && task.status !== 'completed'
                  ).length;

                  const highPriorityTasks = userTasks.filter(task => task.priority === 'high').length;

                  const recentActivity = userTasks.filter(task =>
                    new Date(task.updated_at) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
                  ).length;

                  // Calculate performance score (weighted average)
                  const performanceScore = Math.round(
                    completionRate * 0.4 + // 40% weight on completion rate
                    averageProgress * 0.4 + // 40% weight on average progress
                    (totalTasks > 0 ? Math.max(0, 100 - (overdueTasks / totalTasks) * 100) : 100) * 0.2 // 20% weight on timeliness
                  );

                  return (
                    <>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
                        {/* Tasks Assigned */}
                        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-6 border border-blue-200">
                          <div className="flex items-center gap-3 mb-3">
                            <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
                              <FileText className="w-5 h-5 text-white" />
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-blue-900">{totalTasks}</div>
                              <div className="text-sm text-blue-700 font-medium">Tasks Assigned</div>
                            </div>
                          </div>
                        </div>

                        {/* Completion Rate */}
                        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6 border border-green-200">
                          <div className="flex items-center gap-3 mb-3">
                            <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center">
                              <BarChart3 className="w-5 h-5 text-white" />
                            </div>
                            <div className="flex-1">
                              <div className="text-2xl font-bold text-green-900">{completionRate}%</div>
                              <div className="text-sm text-green-700 font-medium mb-2">Completion Rate</div>
                              <div className="w-full bg-green-200 rounded-full h-2">
                                <div
                                  className="bg-green-500 h-2 rounded-full transition-all duration-300"
                                  style={{ width: `${completionRate}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Performance Score */}
                        <div className={`bg-gradient-to-br rounded-xl p-6 border ${
                          performanceScore >= 80 ? 'from-green-50 to-green-100 border-green-200' :
                          performanceScore >= 60 ? 'from-blue-50 to-blue-100 border-blue-200' :
                          performanceScore >= 40 ? 'from-yellow-50 to-yellow-100 border-yellow-200' :
                          'from-red-50 to-red-100 border-red-200'
                        }`}>
                          <div className="flex items-center gap-3 mb-3">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                              performanceScore >= 80 ? 'bg-green-500' :
                              performanceScore >= 60 ? 'bg-blue-500' :
                              performanceScore >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                            }`}>
                              <BarChart3 className="w-5 h-5 text-white" />
                            </div>
                            <div>
                              <div className={`text-2xl font-bold ${
                                performanceScore >= 80 ? 'text-green-900' :
                                performanceScore >= 60 ? 'text-blue-900' :
                                performanceScore >= 40 ? 'text-yellow-900' : 'text-red-900'
                              }`}>
                                {performanceScore}%
                              </div>
                              <div className={`text-sm font-medium ${
                                performanceScore >= 80 ? 'text-green-700' :
                                performanceScore >= 60 ? 'text-blue-700' :
                                performanceScore >= 40 ? 'text-yellow-700' : 'text-red-700'
                              }`}>
                                {performanceScore >= 80 ? 'Excellent' :
                                 performanceScore >= 60 ? 'Good' :
                                 performanceScore >= 40 ? 'Average' : 'Needs Improvement'}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Detailed Analytics Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                        {/* Task Status Breakdown */}
                        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                          <h4 className="text-lg font-semibold text-slate-900 mb-4">Task Status Breakdown</h4>
                          <div className="space-y-3">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-slate-600">Completed:</span>
                              <span className="px-3 py-1 bg-green-100 text-green-800 text-sm font-medium rounded-full">
                                {completedTasks}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-slate-600">In Progress:</span>
                              <span className="px-3 py-1 bg-blue-100 text-blue-800 text-sm font-medium rounded-full">
                                {inProgressTasks}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-slate-600">Not Started:</span>
                              <span className="px-3 py-1 bg-slate-100 text-slate-800 text-sm font-medium rounded-full">
                                {notStartedTasks}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Priority & Overdue */}
                        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                          <h4 className="text-lg font-semibold text-slate-900 mb-4">Priority & Timeline</h4>
                          <div className="space-y-3">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-slate-600">High Priority Tasks:</span>
                              <span className="px-3 py-1 bg-orange-100 text-orange-800 text-sm font-medium rounded-full">
                                {highPriorityTasks}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-slate-600">Overdue Tasks:</span>
                              <span className="px-3 py-1 bg-red-100 text-red-800 text-sm font-medium rounded-full">
                                {overdueTasks}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-slate-600">Recent Activity:</span>
                              <span className="px-3 py-1 bg-purple-100 text-purple-800 text-sm font-medium rounded-full">
                                {recentActivity} (7 days)
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Average Progress */}
                      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm mb-8">
                        <h4 className="text-lg font-semibold text-slate-900 mb-4">Average Progress Across All Tasks</h4>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-slate-700">Overall Progress</span>
                            <span className="text-lg font-bold text-slate-900">{averageProgress}%</span>
                          </div>
                          <div className="w-full bg-slate-200 rounded-full h-4">
                            <div
                              className="bg-gradient-to-r from-blue-500 to-indigo-500 h-4 rounded-full transition-all duration-300"
                              style={{ width: `${averageProgress}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>

              {/* Individual Tasks Section */}
              <div>
                <h3 className="text-xl font-bold text-slate-900 mb-6">Individual Tasks ({userTasks.length})</h3>
                <div className="space-y-4">
                  {userTasks.length > 0 ? userTasks.map(task => (
                    <div key={task.id} className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="font-semibold text-slate-900 mb-2">{task.title}</h4>
                          <p className="text-sm text-slate-600 mb-3 line-clamp-2">{task.description}</p>
                          <div className="flex items-center gap-4 text-xs text-slate-500">
                            <span>Status: <span className="font-medium text-slate-900">{task.status.replace('_', ' ')}</span></span>
                            <span>Priority: <span className="font-medium text-slate-900">{task.priority}</span></span>
                            <span>Progress: <span className="font-medium text-slate-900">{task.progress_percentage}%</span></span>
                            <span>Due: <span className="font-medium text-slate-900">
                              {task.due_date ? new Date(task.due_date).toLocaleDateString() : 'No due date'}
                            </span></span>
                          </div>
                        </div>
                        <div className="ml-4">
                          <div className="w-16 h-2 bg-slate-200 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"
                              style={{ width: `${task.progress_percentage}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  )) : (
                    <div className="text-center py-8 text-slate-500">
                      <div className="text-lg font-medium mb-2">No tasks assigned to this user</div>
                      <div className="text-sm">This user currently has no task assignments.</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// User Management Tab Component
const UserManagementTab = ({ users, onUpdate }) => {
  const [showCreateModal, setShowCreateModal] = useState(false);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-green-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">User Management</h2>
            <p className="text-sm text-slate-500">Manage system users and permissions</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:shadow-lg transition-all font-medium"
          >
            Add User
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">User</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Email</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Role</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Last Active</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {users.map(user => (
              <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                      {user.first_name[0]}{user.last_name[0]}
                    </div>
                    <div>
                      <div className="font-medium text-slate-900">{user.first_name} {user.last_name}</div>
                      <div className="text-sm text-slate-500">{user.username}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-slate-900">{user.email}</td>
                <td className="px-6 py-4">
                  <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded-full">
                    {user.role || 'User'}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className="px-2 py-1 bg-green-100 text-green-800 text-xs font-medium rounded-full">
                    Active
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-slate-500">
                  {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                </td>
                <td className="px-6 py-4">
                  <div className="flex gap-2">
                    <button className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors">
                      Edit
                    </button>
                    <button className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 transition-colors">
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Reports Management Tab Component
const ReportsManagementTab = ({ reports, onUpdate }) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-purple-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Daily Reports</h2>
            <p className="text-sm text-slate-500">View and manage daily reports</p>
          </div>
          <button className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:shadow-lg transition-all font-medium">
            Export Reports
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Report</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Submitted By</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Date</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {reports.length > 0 ? reports.map(report => (
              <tr key={report.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-4">
                  <div>
                    <div className="font-medium text-slate-900">{report.title || 'Daily Report'}</div>
                    <div className="text-sm text-slate-500 line-clamp-1">{report.content || report.description}</div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 bg-gradient-to-br from-purple-500 to-indigo-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                      {report.submitted_by_first_name ? report.submitted_by_first_name[0] : '?'}
                    </div>
                    <span className="text-sm text-slate-900">
                      {report.submitted_by_first_name} {report.submitted_by_last_name}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-slate-900">
                  {report.created_at ? new Date(report.created_at).toLocaleDateString() : 'N/A'}
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    report.reviewed
                      ? 'bg-green-100 text-green-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {report.reviewed ? 'Reviewed' : 'Pending'}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="flex gap-2">
                    <button className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors">
                      View
                    </button>
                    {!report.reviewed && (
                      <button className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition-colors">
                        Mark Reviewed
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan="5" className="px-6 py-8 text-center text-slate-500">
                  No reports available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Comments Management Tab Component
const CommentsManagementTab = ({ comments, onUpdate }) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Comments Management</h2>
            <p className="text-sm text-slate-500">View and manage system comments</p>
          </div>
          <button className="px-4 py-2 bg-gradient-to-r from-indigo-600 to-blue-600 text-white rounded-lg hover:shadow-lg transition-all font-medium">
            Export Comments
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Comment</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Author</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Task</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Date</th>
              <th className="px-6 py-3 text-left text-xs font-bold text-slate-900 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {comments.length > 0 ? comments.map(comment => (
              <tr key={comment.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-4">
                  <div className="text-sm text-slate-900 line-clamp-2">{comment.content}</div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 bg-gradient-to-br from-indigo-500 to-blue-500 rounded-full flex items-center justify-center text-white text-xs font-medium">
                      {comment.author_first_name ? comment.author_first_name[0] : '?'}
                    </div>
                    <span className="text-sm text-slate-900">
                      {comment.author_first_name} {comment.author_last_name}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-slate-900">
                  {comment.task_title || 'N/A'}
                </td>
                <td className="px-6 py-4 text-sm text-slate-900">
                  {comment.created_at ? new Date(comment.created_at).toLocaleDateString() : 'N/A'}
                </td>
                <td className="px-6 py-4">
                  <div className="flex gap-2">
                    <button className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors">
                      View
                    </button>
                    <button className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 transition-colors">
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan="5" className="px-6 py-8 text-center text-slate-500">
                  No comments available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// Confirm Modal Component
const ConfirmModal = ({ config, onClose }) => {
  const getIcon = () => {
    switch (config.type) {
      case 'danger':
        return <AlertCircle className="w-6 h-6 text-red-600" />;
      case 'warning':
        return <AlertTriangle className="w-6 h-6 text-amber-600" />;
      case 'success':
        return <CheckCircle className="w-6 h-6 text-green-600" />;
      default:
        return <AlertCircle className="w-6 h-6 text-blue-600" />;
    }
  };

  const getButtonStyles = () => {
    switch (config.type) {
      case 'danger':
        return 'bg-red-600 hover:bg-red-700 focus:ring-red-500';
      case 'warning':
        return 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500';
      case 'success':
        return 'bg-green-600 hover:bg-green-700 focus:ring-green-500';
      default:
        return 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500';
    }
  };

  const handleConfirm = () => {
    config.onConfirm();
    onClose();
  };

  const handleCancel = () => {
    config.onCancel();
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-slate-100 rounded-xl flex items-center justify-center">
              {getIcon()}
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">{config.title}</h2>
              <p className="text-sm text-slate-500 mt-1">Please confirm your action</p>
            </div>
          </div>
        </div>

        <div className="p-6">
          <p className="text-slate-700 leading-relaxed">{config.message}</p>
        </div>

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            onClick={handleConfirm}
            className={`flex-1 px-6 py-3 text-white rounded-lg font-medium transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 ${getButtonStyles()}`}
          >
            {config.confirmText}
          </button>
          <button
            onClick={handleCancel}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
          >
            {config.cancelText}
          </button>
        </div>
      </div>
    </div>
  );
};

// Bulk Create Tasks Modal Component
const BulkCreateTasksModal = ({ onClose, onTasksCreated }) => {
  const [tasks, setTasks] = useState([
    {
      title: '',
      description: '',
      assigned_to_id: '',
      start_date: '',
      due_date: '',
      priority: 'medium',
      status: 'not_started'
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [errors, setErrors] = useState([]);
  const [excelFile, setExcelFile] = useState(null);
  const [excelData, setExcelData] = useState([]);
  const [columnMapping, setColumnMapping] = useState({
    title: '',
    description: '',
    assigned_to_id: '',
    start_date: '',
    due_date: '',
    priority: '',
    status: ''
  });
  const [showColumnMapping, setShowColumnMapping] = useState(false);
  const [uploadMode, setUploadMode] = useState('manual'); // 'manual' or 'excel'

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await authAPI.getUsers();
        setUsers(response.data.results || []);
      } catch (error) {
        console.error('Error fetching users:', error);
      } finally {
        setUsersLoading(false);
      }
    };

    fetchUsers();
  }, []);

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      setExcelFile(file);
      parseExcelFile(file);
    }
  };

  const parseExcelFile = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[sheetName];
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

      if (jsonData.length > 0) {
        const headers = jsonData[0];
        const rows = jsonData.slice(1).filter(row => row.some(cell => cell !== undefined && cell !== ''));

        setExcelData(rows);
        setShowColumnMapping(true);

        // Auto-detect column mapping based on common headers
        const autoMapping = {};
        headers.forEach((header, index) => {
          const headerLower = header?.toString().toLowerCase().trim();
          if (headerLower?.includes('title') || headerLower?.includes('task')) {
            autoMapping.title = header;
          } else if (headerLower?.includes('description') || headerLower?.includes('desc')) {
            autoMapping.description = header;
          } else if (headerLower?.includes('assigned') || headerLower?.includes('assignee') || headerLower?.includes('user')) {
            autoMapping.assigned_to_id = header;
          } else if (headerLower?.includes('start') || headerLower?.includes('begin')) {
            autoMapping.start_date = header;
          } else if (headerLower?.includes('due') || headerLower?.includes('deadline') || headerLower?.includes('end')) {
            autoMapping.due_date = header;
          } else if (headerLower?.includes('priority') || headerLower?.includes('prio')) {
            autoMapping.priority = header;
          } else if (headerLower?.includes('status') || headerLower?.includes('state')) {
            autoMapping.status = header;
          }
        });

        setColumnMapping(autoMapping);
      }
    };
    reader.readAsArrayBuffer(file);
  };

  const downloadTemplate = () => {
    // Create template data
    const templateData = [
      ['Title', 'Description', 'Start Date', 'Due Date', 'Priority', 'Status'],
      ['Implement user authentication', 'Build login and registration system with JWT tokens', '2025-01-15', '2025-01-30', 'high', 'not_started'],
      ['Design database schema', 'Create ERD and define all tables and relationships', '2025-01-16', '2025-01-25', 'medium', 'in_progress'],
      ['Setup CI/CD pipeline', 'Configure automated testing and deployment', '2025-01-20', '2025-02-05', 'medium', 'not_started'],
      ['Create API documentation', 'Write comprehensive API docs with examples', '2025-01-18', '2025-01-28', 'low', 'completed'],
      ['Implement payment gateway', 'Integrate Stripe payment processing', '2025-01-22', '2025-02-10', 'high', 'not_started'],
      ['Build admin dashboard', 'Create responsive admin interface', '2025-01-25', '2025-02-15', 'medium', 'not_started'],
      ['Setup monitoring and logging', 'Implement application monitoring and error tracking', '2025-01-28', '2025-02-08', 'low', 'not_started'],
      ['Performance optimization', 'Optimize database queries and API responses', '2025-02-01', '2025-02-20', 'medium', 'not_started']
    ];

    // Create workbook and worksheet
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(templateData);

    // Set column widths
    ws['!cols'] = [
      { wch: 30 }, // Title
      { wch: 50 }, // Description
      { wch: 12 }, // Start Date
      { wch: 12 }, // Due Date
      { wch: 10 }, // Priority
      { wch: 15 }  // Status
    ];

    // Add worksheet to workbook
    XLSX.utils.book_append_sheet(wb, ws, 'Task Template');

    // Generate filename with current date
    const date = new Date().toISOString().split('T')[0];
    const filename = `task_bulk_import_template_${date}.xlsx`;

    // Save file
    XLSX.writeFile(wb, filename);
  };

  const applyColumnMapping = () => {
    if (excelData.length === 0) return;

    const headers = excelData[0] || [];
    const mappedTasks = excelData.map(row => {
      const task = {
        title: '',
        description: '',
        assigned_to_id: '',
        start_date: '',
        due_date: '',
        priority: 'medium',
        status: 'not_started'
      };

      // Map columns to task fields
      headers.forEach((header, index) => {
        const value = row[index]?.toString().trim() || '';

        if (columnMapping.title === header && value) {
          task.title = value;
        } else if (columnMapping.description === header && value) {
          task.description = value;
        } else if (columnMapping.assigned_to_id === header && value) {
          // Try to find user by email or name
          const user = users.find(u =>
            u.email.toLowerCase() === value.toLowerCase() ||
            `${u.first_name} ${u.last_name}`.toLowerCase() === value.toLowerCase()
          );
          task.assigned_to_id = user ? user.id : value;
        } else if (columnMapping.start_date === header && value) {
          // Try to parse date
          const date = new Date(value);
          if (!isNaN(date.getTime())) {
            task.start_date = date.toISOString().split('T')[0];
          }
        } else if (columnMapping.due_date === header && value) {
          // Try to parse date
          const date = new Date(value);
          if (!isNaN(date.getTime())) {
            task.due_date = date.toISOString().split('T')[0];
          }
        } else if (columnMapping.priority === header && value) {
          const priorityLower = value.toLowerCase();
          if (['low', 'medium', 'high'].includes(priorityLower)) {
            task.priority = priorityLower;
          }
        } else if (columnMapping.status === header && value) {
          const statusLower = value.toLowerCase().replace(/\s+/g, '_');
          if (['not_started', 'in_progress', 'completed', 'blocked'].includes(statusLower)) {
            task.status = statusLower;
          }
        }
      });

      return task;
    });

    setTasks(mappedTasks);
    setShowColumnMapping(false);
    setUploadMode('excel');
  };

  const addTask = () => {
    setTasks([...tasks, {
      title: '',
      description: '',
      assigned_to_id: '',
      start_date: '',
      due_date: '',
      priority: 'medium',
      status: 'not_started'
    }]);
  };

  const removeTask = (index) => {
    if (tasks.length > 1) {
      setTasks(tasks.filter((_, i) => i !== index));
    }
  };

  const updateTask = (index, field, value) => {
    const updatedTasks = [...tasks];
    updatedTasks[index][field] = value;
    setTasks(updatedTasks);
  };

  const validateTasks = () => {
    const newErrors = [];
    tasks.forEach((task, index) => {
      if (!task.title.trim()) {
        newErrors.push(`Task ${index + 1}: Title is required`);
      }
    });
    setErrors(newErrors);
    return newErrors.length === 0;
  };

  const resetModal = () => {
    setTasks([{
      title: '',
      description: '',
      assigned_to_id: '',
      start_date: '',
      due_date: '',
      priority: 'medium',
      status: 'not_started'
    }]);
    setExcelFile(null);
    setExcelData([]);
    setColumnMapping({
      title: '',
      description: '',
      assigned_to_id: '',
      start_date: '',
      due_date: '',
      priority: '',
      status: ''
    });
    setShowColumnMapping(false);
    setUploadMode('manual');
    setErrors([]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateTasks()) {
      return;
    }

    setLoading(true);
    setProgress({ current: 0, total: tasks.length });
    setErrors([]);

    try {
      // Prepare tasks data (remove empty fields)
      const tasksData = tasks.map(task => ({
        ...task,
        description: task.description.trim() || undefined,
        assigned_to_id: task.assigned_to_id.trim() || undefined,
        start_date: task.start_date || undefined,
        due_date: task.due_date || undefined,
      })).filter(task => task.title.trim());

      const response = await taskAPI.bulkCreateTasks(tasksData);

      setProgress({ current: tasks.length, total: tasks.length });
      onTasksCreated();

    } catch (error) {
      console.error('Error creating tasks:', error);
      if (error.response?.data?.detail) {
        setErrors([error.response.data.detail]);
      } else {
        setErrors(['Failed to create tasks. Please try again.']);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden">
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Bulk Create Tasks</h2>
              <p className="text-sm text-slate-500 mt-1">Create multiple tasks at once</p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          {/* Upload Mode Selection */}
          <div className="mb-6">
            <div className="flex gap-4 mb-4">
              <button
                type="button"
                onClick={() => {
                  setUploadMode('manual');
                  setTasks([{
                    title: '',
                    description: '',
                    assigned_to_id: '',
                    start_date: '',
                    due_date: '',
                    priority: 'medium',
                    status: 'not_started'
                  }]);
                  setExcelFile(null);
                  setExcelData([]);
                  setErrors([]);
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  uploadMode === 'manual'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <Plus className="w-4 h-4" />
                Manual Entry
              </button>
              <button
                type="button"
                onClick={() => {
                  setUploadMode('excel');
                  setTasks([]);
                  setErrors([]);
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  uploadMode === 'excel'
                    ? 'bg-green-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <FileSpreadsheet className="w-4 h-4" />
                Upload Excel
              </button>
            </div>

            {uploadMode === 'excel' && (
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <Upload className="w-5 h-5 text-slate-600" />
                    <div>
                      <h4 className="font-semibold text-slate-900">Upload Excel File</h4>
                      <p className="text-sm text-slate-600">Select an Excel file (.xlsx, .xls) to import tasks</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={downloadTemplate}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Download Template
                  </button>
                </div>
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleFileUpload}
                  className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {excelFile && (
                  <div className="mt-2 text-sm text-slate-600">
                    Selected: {excelFile.name}
                  </div>
                )}
                <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <h5 className="text-sm font-semibold text-blue-900 mb-1">Template Format:</h5>
                  <p className="text-xs text-blue-700">
                    Use columns: Title*, Description, Start Date, Due Date, Priority (low/medium/high), Status (not_started/in_progress/completed/blocked)
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Progress Bar */}
          {loading && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700">
                  Creating tasks... ({progress.current}/{progress.total})
                </span>
                <span className="text-sm text-slate-500">
                  {Math.round((progress.current / progress.total) * 100)}%
                </span>
              </div>
              <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-300"
                  style={{ width: `${(progress.current / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Errors */}
          {errors.length > 0 && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <h3 className="text-sm font-semibold text-red-800 mb-2">Errors:</h3>
              <ul className="text-sm text-red-700 space-y-1">
                {errors.map((error, index) => (
                  <li key={index}>• {error}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Tasks List */}
          {uploadMode === 'manual' ? (
            <div className="space-y-6">
              {tasks.map((task, index) => (
                <div key={index} className="border border-slate-200 rounded-xl p-6 bg-slate-50/50">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-slate-900">Task {index + 1}</h3>
                    {tasks.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeTask(index)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Remove task"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="md:col-span-2">
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Title *
                      </label>
                      <input
                        type="text"
                        className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={task.title}
                        onChange={(e) => updateTask(index, 'title', e.target.value)}
                        placeholder="Enter task title..."
                        required
                      />
                    </div>

                    <div className="md:col-span-2">
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Description
                      </label>
                      <textarea
                        className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                        value={task.description}
                        onChange={(e) => updateTask(index, 'description', e.target.value)}
                        placeholder="Describe the task..."
                        rows="2"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Assign To (Optional)
                      </label>
                      <select
                        className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={task.assigned_to_id}
                        onChange={(e) => updateTask(index, 'assigned_to_id', e.target.value)}
                        disabled={usersLoading}
                      >
                        <option value="">Leave unassigned</option>
                        {users.map(user => (
                          <option key={user.id} value={user.id}>
                            {user.first_name} {user.last_name} ({user.email})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Priority
                      </label>
                      <select
                        className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={task.priority}
                        onChange={(e) => updateTask(index, 'priority', e.target.value)}
                      >
                        <option value="low">Low Priority</option>
                        <option value="medium">Medium Priority</option>
                        <option value="high">High Priority</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Start Date
                      </label>
                      <input
                        type="date"
                        className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={task.start_date}
                        onChange={(e) => updateTask(index, 'start_date', e.target.value)}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Due Date
                      </label>
                      <input
                        type="date"
                        className="w-full px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={task.due_date}
                        onChange={(e) => updateTask(index, 'due_date', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* Excel Import Preview */
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-200 bg-slate-50">
                <h3 className="text-lg font-semibold text-slate-900">
                  Import Preview ({tasks.length} tasks)
                </h3>
                <p className="text-sm text-slate-500 mt-1">
                  Review and edit tasks before importing
                </p>
              </div>

              <div className="overflow-x-auto max-h-96">
                <table className="w-full">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Title</th>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Description</th>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Assigned To</th>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Priority</th>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Start Date</th>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Due Date</th>
                      <th className="px-4 py-3 text-left text-xs font-bold text-slate-900 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {tasks.map((task, index) => (
                      <tr key={index} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <input
                            type="text"
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                            value={task.title}
                            onChange={(e) => updateTask(index, 'title', e.target.value)}
                            placeholder="Task title..."
                          />
                        </td>
                        <td className="px-4 py-3">
                          <textarea
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                            value={task.description}
                            onChange={(e) => updateTask(index, 'description', e.target.value)}
                            placeholder="Description..."
                            rows="1"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <select
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                            value={task.assigned_to_id}
                            onChange={(e) => updateTask(index, 'assigned_to_id', e.target.value)}
                            disabled={usersLoading}
                          >
                            <option value="">Unassigned</option>
                            {users.map(user => (
                              <option key={user.id} value={user.id}>
                                {user.first_name} {user.last_name}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          <select
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                            value={task.priority}
                            onChange={(e) => updateTask(index, 'priority', e.target.value)}
                          >
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          <select
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                            value={task.status}
                            onChange={(e) => updateTask(index, 'status', e.target.value)}
                          >
                            <option value="not_started">Not Started</option>
                            <option value="in_progress">In Progress</option>
                            <option value="completed">Completed</option>
                            <option value="blocked">Blocked</option>
                          </select>
                        </td>
                        <td className="px-4 py-3">
                          <input
                            type="date"
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                            value={task.start_date}
                            onChange={(e) => updateTask(index, 'start_date', e.target.value)}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <input
                            type="date"
                            className="w-full px-2 py-1 bg-white border border-slate-200 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                            value={task.due_date}
                            onChange={(e) => updateTask(index, 'due_date', e.target.value)}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => removeTask(index)}
                            className="p-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                            title="Remove task"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Add Task Button */}
          {uploadMode === 'manual' && (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={addTask}
                className="flex items-center gap-2 px-6 py-3 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors font-medium"
              >
                <Plus className="w-4 h-4" />
                Add Another Task
              </button>
            </div>
          )}
        </form>

        {/* Column Mapping Modal */}
        {showColumnMapping && excelData.length > 0 && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
              <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900">Map Excel Columns</h2>
                    <p className="text-sm text-slate-500 mt-1">Map your Excel columns to task fields</p>
                  </div>
                  <button
                    onClick={() => setShowColumnMapping(false)}
                    className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Detected Columns</h3>
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                      {excelData[0]?.map((header, index) => (
                        <div key={index} className="px-3 py-2 bg-white border border-slate-200 rounded text-sm font-medium text-slate-700">
                          {header || `Column ${index + 1}`}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-slate-900">Column Mapping</h3>

                  {Object.keys(columnMapping).map(field => (
                    <div key={field} className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                      <label className="text-sm font-semibold text-slate-900 capitalize">
                        {field.replace('_', ' ')}:
                      </label>
                      <select
                        className="px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        value={columnMapping[field]}
                        onChange={(e) => setColumnMapping({
                          ...columnMapping,
                          [field]: e.target.value
                        })}
                      >
                        <option value="">Select column...</option>
                        {excelData[0]?.map((header, index) => (
                          <option key={index} value={header}>
                            {header || `Column ${index + 1}`}
                          </option>
                        ))}
                      </select>
                      <div className="text-xs text-slate-500">
                        {field === 'title' && 'Required field'}
                        {field === 'description' && 'Optional text description'}
                        {field === 'assigned_to_id' && 'User email or name'}
                        {field === 'start_date' && 'Date format'}
                        {field === 'due_date' && 'Date format'}
                        {field === 'priority' && 'low/medium/high'}
                        {field === 'status' && 'not_started/in_progress/completed/blocked'}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <h4 className="text-sm font-semibold text-blue-900 mb-2">Preview</h4>
                  <p className="text-sm text-blue-700">
                    First row will create {excelData.length} task{excelData.length !== 1 ? 's' : ''}.
                    Make sure the Title column is mapped for successful import.
                  </p>
                </div>
              </div>

              <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
                <button
                  onClick={() => setShowColumnMapping(false)}
                  className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={applyColumnMapping}
                  className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:shadow-lg transition-all font-medium"
                >
                  Apply Mapping & Import
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="p-6 border-t border-slate-200 bg-slate-50 flex gap-3">
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading || tasks.length === 0 || (uploadMode === 'excel' && !excelFile)}
            className="flex-1 px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all font-medium"
          >
            {loading
              ? `Creating Tasks... (${progress.current}/${progress.total})`
              : uploadMode === 'excel'
                ? `Import ${tasks.length} Task${tasks.length !== 1 ? 's' : ''} from Excel`
                : `Create ${tasks.length} Task${tasks.length !== 1 ? 's' : ''}`
            }
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-6 py-3 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-all font-medium disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Settings Tab Component
const SettingsTab = () => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
      <div className="text-center py-12">
        <Settings className="w-16 h-16 text-slate-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-slate-900 mb-2">Settings</h3>
        <p className="text-slate-500">System settings and configuration options will be available here.</p>
      </div>
    </div>
  );
};

export default AdminDashboard;
