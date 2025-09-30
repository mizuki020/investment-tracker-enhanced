import { useState, useEffect } from "react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Area,
  AreaChart
} from "recharts";
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Calendar,
  DollarSign,
  Award,
  AlertTriangle,
  BarChart3
} from "lucide-react";

const Analytics = () => {
  const [records, setRecords] = useState([]);
  const [analytics, setAnalytics] = useState({
    totalTrades: 0,
    winRate: 0,
    totalProfit: 0,
    averageProfit: 0,
    bestTrade: 0,
    worstTrade: 0,
    profitByMonth: [],
    predictionAccuracy: [],
    sectorPerformance: [],
    timeframeAnalysis: []
  });

  const [selectedTimeframe, setSelectedTimeframe] = useState("all");
  const [selectedMetric, setSelectedMetric] = useState("profit");

  // データの初期化と分析
  useEffect(() => {
    // ローカルストレージから記録を読み込み
    const savedRecords = localStorage.getItem('investmentRecords');
    let recordsData = [];
    
    if (savedRecords) {
      recordsData = JSON.parse(savedRecords);
    } else {
      // サンプルデータ
      recordsData = [
        {
          id: 1,
          symbol: "7203",
          companyName: "トヨタ自動車",
          date: "2025-09-29",
          investmentAmount: 100000,
          prediction: "上昇",
          result: "成功",
          actualProfit: 15000,
          timeframe: "中期（1ヶ月以内）",
          sector: "自動車"
        },
        {
          id: 2,
          symbol: "6758",
          companyName: "ソニーグループ",
          date: "2025-09-28",
          investmentAmount: 80000,
          prediction: "下降",
          result: "失敗",
          actualProfit: -8000,
          timeframe: "短期（1週間以内）",
          sector: "テクノロジー"
        },
        {
          id: 3,
          symbol: "9984",
          companyName: "ソフトバンクグループ",
          date: "2025-09-27",
          investmentAmount: 150000,
          prediction: "上昇",
          result: "成功",
          actualProfit: 22000,
          timeframe: "長期（3ヶ月以上）",
          sector: "テクノロジー"
        },
        {
          id: 4,
          symbol: "8306",
          companyName: "三菱UFJフィナンシャル・グループ",
          date: "2025-09-25",
          investmentAmount: 120000,
          prediction: "上昇",
          result: "成功",
          actualProfit: 8000,
          timeframe: "中期（1ヶ月以内）",
          sector: "金融"
        },
        {
          id: 5,
          symbol: "4502",
          companyName: "武田薬品工業",
          date: "2025-09-20",
          investmentAmount: 90000,
          prediction: "横ばい",
          result: "失敗",
          actualProfit: -5000,
          timeframe: "長期（3ヶ月以上）",
          sector: "ヘルスケア"
        }
      ];
    }

    setRecords(recordsData);
    calculateAnalytics(recordsData);
  }, []);

  const calculateAnalytics = (recordsData) => {
    const completedTrades = recordsData.filter(record => record.result && record.actualProfit !== undefined);
    
    if (completedTrades.length === 0) {
      return;
    }

    // 基本統計
    const totalTrades = completedTrades.length;
    const successfulTrades = completedTrades.filter(record => record.result === "成功").length;
    const winRate = (successfulTrades / totalTrades) * 100;
    const totalProfit = completedTrades.reduce((sum, record) => sum + (record.actualProfit || 0), 0);
    const averageProfit = totalProfit / totalTrades;
    const bestTrade = Math.max(...completedTrades.map(record => record.actualProfit || 0));
    const worstTrade = Math.min(...completedTrades.map(record => record.actualProfit || 0));

    // 月別利益
    const profitByMonth = {};
    completedTrades.forEach(record => {
      const month = record.date.substring(0, 7); // YYYY-MM
      profitByMonth[month] = (profitByMonth[month] || 0) + (record.actualProfit || 0);
    });

    const profitByMonthArray = Object.entries(profitByMonth).map(([month, profit]) => ({
      month,
      profit,
      formattedMonth: new Date(month + "-01").toLocaleDateString('ja-JP', { year: 'numeric', month: 'short' })
    })).sort((a, b) => a.month.localeCompare(b.month));

    // 予想精度分析
    const predictionTypes = ["上昇", "下降", "横ばい"];
    const predictionAccuracy = predictionTypes.map(prediction => {
      const predictionTrades = completedTrades.filter(record => record.prediction === prediction);
      const successfulPredictions = predictionTrades.filter(record => record.result === "成功").length;
      const accuracy = predictionTrades.length > 0 ? (successfulPredictions / predictionTrades.length) * 100 : 0;
      
      return {
        prediction,
        accuracy,
        total: predictionTrades.length,
        successful: successfulPredictions
      };
    });

    // セクター別パフォーマンス
    const sectorData = {};
    completedTrades.forEach(record => {
      const sector = record.sector || "その他";
      if (!sectorData[sector]) {
        sectorData[sector] = { profit: 0, trades: 0, successful: 0 };
      }
      sectorData[sector].profit += record.actualProfit || 0;
      sectorData[sector].trades += 1;
      if (record.result === "成功") {
        sectorData[sector].successful += 1;
      }
    });

    const sectorPerformance = Object.entries(sectorData).map(([sector, data]) => ({
      sector,
      profit: data.profit,
      trades: data.trades,
      winRate: (data.successful / data.trades) * 100,
      averageProfit: data.profit / data.trades
    }));

    // 投資期間別分析
    const timeframeData = {};
    completedTrades.forEach(record => {
      const timeframe = record.timeframe || "未設定";
      if (!timeframeData[timeframe]) {
        timeframeData[timeframe] = { profit: 0, trades: 0, successful: 0 };
      }
      timeframeData[timeframe].profit += record.actualProfit || 0;
      timeframeData[timeframe].trades += 1;
      if (record.result === "成功") {
        timeframeData[timeframe].successful += 1;
      }
    });

    const timeframeAnalysis = Object.entries(timeframeData).map(([timeframe, data]) => ({
      timeframe,
      profit: data.profit,
      trades: data.trades,
      winRate: (data.successful / data.trades) * 100,
      averageProfit: data.profit / data.trades
    }));

    setAnalytics({
      totalTrades,
      winRate,
      totalProfit,
      averageProfit,
      bestTrade,
      worstTrade,
      profitByMonth: profitByMonthArray,
      predictionAccuracy,
      sectorPerformance,
      timeframeAnalysis
    });
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const StatCard = ({ title, value, icon: Icon, trend, color = "blue", subtitle }) => {
    const colorClasses = {
      blue: "bg-blue-50 text-blue-600 border-blue-200",
      green: "bg-green-50 text-green-600 border-green-200",
      red: "bg-red-50 text-red-600 border-red-200",
      purple: "bg-purple-50 text-purple-600 border-purple-200",
      yellow: "bg-yellow-50 text-yellow-600 border-yellow-200"
    };

    return (
      <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition-shadow duration-200">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            {subtitle && (
              <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
            )}
            {trend !== undefined && (
              <div className={`flex items-center mt-2 text-sm ${trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                {trend > 0 ? <TrendingUp className="h-4 w-4 mr-1" /> : trend < 0 ? <TrendingDown className="h-4 w-4 mr-1" /> : null}
                <span>{trend > 0 ? '+' : ''}{trend}%</span>
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

  const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4'];

  return (
    <div className="space-y-8">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">投資分析</h1>
          <p className="text-gray-600 mt-1">投資パフォーマンスの詳細分析</p>
        </div>
        <div className="flex space-x-2">
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">全期間</option>
            <option value="3m">過去3ヶ月</option>
            <option value="6m">過去6ヶ月</option>
            <option value="1y">過去1年</option>
          </select>
        </div>
      </div>

      {/* 統計カード */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="総取引数"
          value={analytics.totalTrades}
          icon={BarChart3}
          color="blue"
        />
        <StatCard
          title="勝率"
          value={`${analytics.winRate.toFixed(1)}%`}
          icon={Target}
          color="green"
          trend={analytics.winRate > 50 ? 5.2 : -2.1}
        />
        <StatCard
          title="総利益"
          value={formatCurrency(analytics.totalProfit)}
          icon={DollarSign}
          color={analytics.totalProfit > 0 ? "green" : "red"}
          trend={12.5}
        />
        <StatCard
          title="平均利益"
          value={formatCurrency(analytics.averageProfit)}
          icon={TrendingUp}
          color={analytics.averageProfit > 0 ? "green" : "red"}
          subtitle={`最高: ${formatCurrency(analytics.bestTrade)}`}
        />
      </div>

      {/* チャートセクション */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 月別利益推移 */}
        <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">月別利益推移</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics.profitByMonth}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="formattedMonth" />
                <YAxis />
                <Tooltip 
                  formatter={(value) => [formatCurrency(value), "利益"]}
                />
                <Area 
                  type="monotone" 
                  dataKey="profit" 
                  stroke="#3B82F6" 
                  fill="#3B82F6"
                  fillOpacity={0.3}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 予想精度分析 */}
        <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">予想精度分析</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.predictionAccuracy}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="prediction" />
                <YAxis />
                <Tooltip 
                  formatter={(value, name) => [
                    name === "accuracy" ? `${value.toFixed(1)}%` : value,
                    name === "accuracy" ? "精度" : "取引数"
                  ]}
                />
                <Bar dataKey="accuracy" fill="#10B981" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* セクター別パフォーマンス */}
        <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">セクター別パフォーマンス</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics.sectorPerformance}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ sector, profit }) => `${sector}: ${formatCurrency(profit)}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="profit"
                >
                  {analytics.sectorPerformance.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatCurrency(value)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 投資期間別分析 */}
        <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">投資期間別分析</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analytics.timeframeAnalysis}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timeframe" />
                <YAxis />
                <Tooltip 
                  formatter={(value, name) => [
                    name === "winRate" ? `${value.toFixed(1)}%` : formatCurrency(value),
                    name === "winRate" ? "勝率" : "平均利益"
                  ]}
                />
                <Bar dataKey="winRate" fill="#3B82F6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* 詳細分析テーブル */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* セクター別詳細 */}
        <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">セクター別詳細</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    セクター
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    取引数
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    勝率
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    総利益
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {analytics.sectorPerformance.map((sector, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {sector.sector}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {sector.trades}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <span className={`font-medium ${
                        sector.winRate > 50 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {sector.winRate.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`font-medium ${
                        sector.profit > 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {formatCurrency(sector.profit)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 投資期間別詳細 */}
        <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">投資期間別詳細</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    期間
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    取引数
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    勝率
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    平均利益
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {analytics.timeframeAnalysis.map((timeframe, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {timeframe.timeframe}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {timeframe.trades}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <span className={`font-medium ${
                        timeframe.winRate > 50 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {timeframe.winRate.toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`font-medium ${
                        timeframe.averageProfit > 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {formatCurrency(timeframe.averageProfit)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* インサイトとアドバイス */}
      <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Award className="h-5 w-5 mr-2 text-blue-600" />
          投資インサイト
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-4 bg-blue-50 rounded-lg">
            <h4 className="font-medium text-blue-900 mb-2">最も成功したセクター</h4>
            <p className="text-blue-700 text-sm">
              {analytics.sectorPerformance.length > 0 && 
                analytics.sectorPerformance.reduce((best, current) => 
                  current.winRate > best.winRate ? current : best
                ).sector
              } セクターで最高の勝率を記録
            </p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg">
            <h4 className="font-medium text-green-900 mb-2">最適な投資期間</h4>
            <p className="text-green-700 text-sm">
              {analytics.timeframeAnalysis.length > 0 && 
                analytics.timeframeAnalysis.reduce((best, current) => 
                  current.averageProfit > best.averageProfit ? current : best
                ).timeframe
              } で最高の平均利益
            </p>
          </div>
          <div className="p-4 bg-yellow-50 rounded-lg">
            <h4 className="font-medium text-yellow-900 mb-2">改善ポイント</h4>
            <p className="text-yellow-700 text-sm">
              {analytics.winRate < 50 
                ? "勝率向上のため、リスク管理を強化しましょう"
                : "良好なパフォーマンスを維持しています"
              }
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
