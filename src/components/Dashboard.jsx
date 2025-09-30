import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Target, 
  PlusCircle,
  BarChart3,
  Calendar,
  Award
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const Dashboard = () => {
  const [stats, setStats] = useState({
    totalInvestments: 0,
    totalProfit: 0,
    winRate: 0,
    activePositions: 0
  });

  const [recentRecords, setRecentRecords] = useState([]);
  const [performanceData, setPerformanceData] = useState([]);

  // サンプルデータの初期化
  useEffect(() => {
    // サンプル統計データ
    setStats({
      totalInvestments: 1250000,
      totalProfit: 125000,
      winRate: 68.5,
      activePositions: 12
    });

    // サンプル最近の記録
    setRecentRecords([
      {
        id: 1,
        symbol: "7203",
        company: "トヨタ自動車",
        date: "2025-09-29",
        prediction: "上昇",
        result: "成功",
        profit: 15000
      },
      {
        id: 2,
        symbol: "6758",
        company: "ソニーグループ",
        date: "2025-09-28",
        prediction: "下降",
        result: "失敗",
        profit: -8000
      },
      {
        id: 3,
        symbol: "9984",
        company: "ソフトバンクグループ",
        date: "2025-09-27",
        prediction: "上昇",
        result: "成功",
        profit: 22000
      }
    ]);

    // サンプルパフォーマンスデータ
    setPerformanceData([
      { date: "09/20", value: 1000000 },
      { date: "09/21", value: 1015000 },
      { date: "09/22", value: 1008000 },
      { date: "09/23", value: 1025000 },
      { date: "09/24", value: 1040000 },
      { date: "09/25", value: 1035000 },
      { date: "09/26", value: 1055000 },
      { date: "09/27", value: 1077000 },
      { date: "09/28", value: 1069000 },
      { date: "09/29", value: 1084000 }
    ]);
  }, []);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const StatCard = ({ title, value, icon: Icon, trend, color = "blue" }) => {
    const colorClasses = {
      blue: "bg-blue-50 text-blue-600 border-blue-200",
      green: "bg-green-50 text-green-600 border-green-200",
      red: "bg-red-50 text-red-600 border-red-200",
      purple: "bg-purple-50 text-purple-600 border-purple-200"
    };

    return (
      <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition-shadow duration-200">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            {trend && (
              <div className={`flex items-center mt-2 text-sm ${trend > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {trend > 0 ? <TrendingUp className="h-4 w-4 mr-1" /> : <TrendingDown className="h-4 w-4 mr-1" />}
                <span>{Math.abs(trend)}%</span>
              </div>
            )}
          </div>
          <div className={`p-3 rounded-full ${colorClasses[color]}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-8">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">ダッシュボード</h1>
          <p className="text-gray-600 mt-1">投資記録と分析の概要</p>
        </div>
        <Link
          to="/add-record"
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200"
        >
          <PlusCircle className="h-5 w-5 mr-2" />
          新しい記録を追加
        </Link>
      </div>

      {/* 統計カード */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="総投資額"
          value={formatCurrency(stats.totalInvestments)}
          icon={DollarSign}
          color="blue"
        />
        <StatCard
          title="総利益"
          value={formatCurrency(stats.totalProfit)}
          icon={TrendingUp}
          trend={12.5}
          color="green"
        />
        <StatCard
          title="勝率"
          value={`${stats.winRate}%`}
          icon={Target}
          trend={5.2}
          color="purple"
        />
        <StatCard
          title="アクティブポジション"
          value={stats.activePositions}
          icon={BarChart3}
          color="blue"
        />
      </div>

      {/* チャートセクション */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* パフォーマンスチャート */}
        <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">ポートフォリオパフォーマンス</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip 
                  formatter={(value) => [formatCurrency(value), "ポートフォリオ価値"]}
                />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke="#3B82F6" 
                  strokeWidth={2}
                  dot={{ fill: "#3B82F6", strokeWidth: 2, r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 最近の記録 */}
        <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">最近の投資記録</h3>
            <Link 
              to="/records" 
              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
            >
              すべて表示
            </Link>
          </div>
          <div className="space-y-3">
            {recentRecords.map((record) => (
              <div key={record.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-gray-900">{record.symbol}</span>
                    <span className="text-sm text-gray-600">{record.company}</span>
                  </div>
                  <div className="flex items-center space-x-2 mt-1">
                    <Calendar className="h-4 w-4 text-gray-400" />
                    <span className="text-sm text-gray-500">{record.date}</span>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      record.result === "成功" 
                        ? "bg-green-100 text-green-800" 
                        : "bg-red-100 text-red-800"
                    }`}>
                      {record.result}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-semibold ${
                    record.profit > 0 ? "text-green-600" : "text-red-600"
                  }`}>
                    {record.profit > 0 ? "+" : ""}{formatCurrency(record.profit)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* クイックアクション */}
      <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">クイックアクション</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link
            to="/add-record"
            className="flex items-center p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors duration-200"
          >
            <PlusCircle className="h-8 w-8 text-blue-600 mr-3" />
            <div>
              <div className="font-medium text-gray-900">新規記録</div>
              <div className="text-sm text-gray-600">投資記録を追加</div>
            </div>
          </Link>
          <Link
            to="/analytics"
            className="flex items-center p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors duration-200"
          >
            <BarChart3 className="h-8 w-8 text-green-600 mr-3" />
            <div>
              <div className="font-medium text-gray-900">分析</div>
              <div className="text-sm text-gray-600">パフォーマンス分析</div>
            </div>
          </Link>
          <Link
            to="/records"
            className="flex items-center p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors duration-200"
          >
            <Calendar className="h-8 w-8 text-purple-600 mr-3" />
            <div>
              <div className="font-medium text-gray-900">記録一覧</div>
              <div className="text-sm text-gray-600">過去の記録を確認</div>
            </div>
          </Link>
          <Link
            to="/settings"
            className="flex items-center p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors duration-200"
          >
            <Award className="h-8 w-8 text-gray-600 mr-3" />
            <div>
              <div className="font-medium text-gray-900">設定</div>
              <div className="text-sm text-gray-600">アプリ設定</div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
