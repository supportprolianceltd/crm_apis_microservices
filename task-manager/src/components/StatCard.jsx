// components/StatCard.jsx
const StatCard = ({ title, value, icon, color = 'blue' }) => {
  const colorClasses = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    red: 'from-red-500 to-red-600',
    orange: 'from-orange-500 to-orange-600',
    purple: 'from-purple-500 to-purple-600',
    indigo: 'from-indigo-500 to-indigo-600'
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm hover:shadow-md transition-all duration-300 group">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-600 mb-1">{title}</p>
          <p className="text-2xl font-bold text-slate-900">{value}</p>
        </div>
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colorClasses[color]} flex items-center justify-center group-hover:scale-110 transition-transform duration-300`}>
          <div className="text-white">
            {icon}
          </div>
        </div>
      </div>
    </div>
  );
};

// components/RecentActivity.jsx
const RecentActivity = ({ tasks }) => {
  const recentTasks = tasks
    .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    .slice(0, 5);

  return (
    <div className="space-y-3">
      {recentTasks.map(task => (
        <div key={task.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50">
          <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-900 truncate">{task.title}</p>
            <p className="text-xs text-slate-500">
              {task.status.replace('_', ' ')} • {new Date(task.updated_at).toLocaleDateString()}
            </p>
          </div>
        </div>
      ))}
      {recentTasks.length === 0 && (
        <p className="text-sm text-slate-500 text-center py-4">No recent activity</p>
      )}
    </div>
  );
};

export { StatCard, TaskStatusChart, RecentActivity };

// components/TaskStatusChart.jsx
const TaskStatusChart = ({ tasks }) => {
  const statusCounts = {
    not_started: tasks.filter(t => t.status === 'not_started').length,
    in_progress: tasks.filter(t => t.status === 'in_progress').length,
    completed: tasks.filter(t => t.status === 'completed').length,
    blocked: tasks.filter(t => t.status === 'blocked').length
  };

  return (
    <div className="space-y-3">
      {Object.entries(statusCounts).map(([status, count]) => (
        <div key={status} className="flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700 capitalize">
            {status.replace('_', ' ')}
          </span>
          <div className="flex items-center gap-3">
            <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${(count / tasks.length) * 100}%` }}
              />
            </div>
            <span className="text-sm font-semibold text-slate-900 w-8">
              {count}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
};