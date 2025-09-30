import { useState, useEffect } from "react";
import { 
  Search, 
  Filter, 
  Calendar, 
  TrendingUp, 
  TrendingDown, 
  Eye,
  Edit,
  Trash2,
  Download,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import { format } from "date-fns";

const RecordsList = () => {
  const [records, setRecords] = useState([]);
  const [filteredRecords, setFilteredRecords] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterPrediction, setFilterPrediction] = useState("");
  const [filterResult, setFilterResult] = useState("");
  const [sortBy, setSortBy] = useState("date");
  const [sortOrder, setSortOrder] = useState("desc");
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  const recordsPerPage = 10;

  // サンプルデータの初期化
  useEffect(() => {
    // ローカルストレージから記録を読み込み、なければサンプルデータを使用
    const savedRecords = localStorage.getItem('investmentRecords');
    const sampleRecords = [
      {
        id: 1,
        symbol: "7203",
        companyName: "トヨタ自動車",
        date: "2025-09-29",
        investmentAmount: 100000,
        prediction: "上昇",
        predictionReason: "決算好調、新型車発表",
        targetPrice: 2500,
        stopLoss: 2000,
        timeframe: "中期（1ヶ月以内）",
        analysis: "四半期決算が予想を上回り、新型電気自動車の発表により株価上昇が期待される。テクニカル的にも上昇トレンドを維持している。",
        result: "成功",
        actualProfit: 15000,
        createdAt: "2025-09-29T10:00:00Z",
        chartImages: []
      },
      {
        id: 2,
        symbol: "6758",
        companyName: "ソニーグループ",
        date: "2025-09-28",
        investmentAmount: 80000,
        prediction: "下降",
        predictionReason: "市場環境悪化",
        targetPrice: 12000,
        stopLoss: 13500,
        timeframe: "短期（1週間以内）",
        analysis: "半導体市場の低迷により、ソニーの業績に影響が出ると予想。チャート上でも下降トレンドが確認できる。",
        result: "失敗",
        actualProfit: -8000,
        createdAt: "2025-09-28T14:30:00Z",
        chartImages: []
      },
      {
        id: 3,
        symbol: "9984",
        companyName: "ソフトバンクグループ",
        date: "2025-09-27",
        investmentAmount: 150000,
        prediction: "上昇",
        predictionReason: "AI投資拡大",
        targetPrice: 6000,
        stopLoss: 5200,
        timeframe: "長期（3ヶ月以上）",
        analysis: "AI関連投資の拡大により、長期的な成長が期待される。Vision Fundの投資先企業の業績も好調。",
        result: "成功",
        actualProfit: 22000,
        createdAt: "2025-09-27T09:15:00Z",
        chartImages: []
      }
    ];

    if (savedRecords) {
      setRecords(JSON.parse(savedRecords));
    } else {
      setRecords(sampleRecords);
    }
  }, []);

  // フィルタリングとソート
  useEffect(() => {
    let filtered = records.filter(record => {
      const matchesSearch = 
        record.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        record.companyName.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesPrediction = !filterPrediction || record.prediction === filterPrediction;
      const matchesResult = !filterResult || record.result === filterResult;

      return matchesSearch && matchesPrediction && matchesResult;
    });

    // ソート
    filtered.sort((a, b) => {
      let aValue, bValue;
      
      switch (sortBy) {
        case "date":
          aValue = new Date(a.date);
          bValue = new Date(b.date);
          break;
        case "symbol":
          aValue = a.symbol;
          bValue = b.symbol;
          break;
        case "profit":
          aValue = a.actualProfit || 0;
          bValue = b.actualProfit || 0;
          break;
        default:
          aValue = a[sortBy];
          bValue = b[sortBy];
      }

      if (sortOrder === "asc") {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    setFilteredRecords(filtered);
    setCurrentPage(1);
  }, [records, searchTerm, filterPrediction, filterResult, sortBy, sortOrder]);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const handleDelete = (id) => {
    if (confirm("この記録を削除しますか？")) {
      const updatedRecords = records.filter(record => record.id !== id);
      setRecords(updatedRecords);
      localStorage.setItem('investmentRecords', JSON.stringify(updatedRecords));
    }
  };

  const handleExport = () => {
    const csvContent = [
      ["銘柄コード", "企業名", "日付", "投資金額", "予想", "結果", "利益"],
      ...filteredRecords.map(record => [
        record.symbol,
        record.companyName,
        record.date,
        record.investmentAmount,
        record.prediction,
        record.result || "未確定",
        record.actualProfit || 0
      ])
    ].map(row => row.join(",")).join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `investment_records_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  // ページネーション
  const totalPages = Math.ceil(filteredRecords.length / recordsPerPage);
  const startIndex = (currentPage - 1) * recordsPerPage;
  const endIndex = startIndex + recordsPerPage;
  const currentRecords = filteredRecords.slice(startIndex, endIndex);

  const DetailModal = ({ record, onClose }) => {
    if (!record) return null;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
          <div className="p-6 border-b border-gray-200">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-900">
                {record.symbol} - {record.companyName}
              </h2>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
          </div>
          
          <div className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-500">投資日</label>
                  <p className="text-lg text-gray-900">{record.date}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">投資金額</label>
                  <p className="text-lg text-gray-900">{formatCurrency(record.investmentAmount)}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">予想</label>
                  <p className={`text-lg font-semibold ${
                    record.prediction === "上昇" ? "text-green-600" : 
                    record.prediction === "下降" ? "text-red-600" : "text-gray-600"
                  }`}>
                    {record.prediction}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">投資期間</label>
                  <p className="text-lg text-gray-900">{record.timeframe}</p>
                </div>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-500">目標価格</label>
                  <p className="text-lg text-gray-900">{record.targetPrice ? `¥${record.targetPrice}` : "未設定"}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">ストップロス</label>
                  <p className="text-lg text-gray-900">{record.stopLoss ? `¥${record.stopLoss}` : "未設定"}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">結果</label>
                  <p className={`text-lg font-semibold ${
                    record.result === "成功" ? "text-green-600" : 
                    record.result === "失敗" ? "text-red-600" : "text-gray-600"
                  }`}>
                    {record.result || "未確定"}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">実際の利益</label>
                  <p className={`text-lg font-semibold ${
                    (record.actualProfit || 0) > 0 ? "text-green-600" : 
                    (record.actualProfit || 0) < 0 ? "text-red-600" : "text-gray-600"
                  }`}>
                    {record.actualProfit ? formatCurrency(record.actualProfit) : "未確定"}
                  </p>
                </div>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-500">予想根拠</label>
              <p className="text-gray-900 mt-1">{record.predictionReason || "記載なし"}</p>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-500">分析・メモ</label>
              <div className="mt-1 p-4 bg-gray-50 rounded-lg">
                <p className="text-gray-900 whitespace-pre-wrap">{record.analysis}</p>
              </div>
            </div>

            {record.chartImages && record.chartImages.length > 0 && (
              <div>
                <label className="text-sm font-medium text-gray-500">チャート画像</label>
                <div className="mt-2 grid grid-cols-2 md:grid-cols-3 gap-4">
                  {record.chartImages.map((image, index) => (
                    <img
                      key={index}
                      src={image.preview}
                      alt={`Chart ${index + 1}`}
                      className="w-full h-32 object-cover rounded-lg border border-gray-200"
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">投資記録一覧</h1>
          <p className="text-gray-600 mt-1">過去の投資記録を確認・管理できます</p>
        </div>
        <button
          onClick={handleExport}
          className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors duration-200"
        >
          <Download className="h-5 w-5 mr-2" />
          CSVエクスポート
        </button>
      </div>

      {/* フィルター・検索 */}
      <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Search className="inline h-4 w-4 mr-1" />
              検索
            </label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="銘柄コードまたは企業名"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Filter className="inline h-4 w-4 mr-1" />
              予想フィルター
            </label>
            <select
              value={filterPrediction}
              onChange={(e) => setFilterPrediction(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">すべて</option>
              <option value="上昇">上昇</option>
              <option value="下降">下降</option>
              <option value="横ばい">横ばい</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              結果フィルター
            </label>
            <select
              value={filterResult}
              onChange={(e) => setFilterResult(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">すべて</option>
              <option value="成功">成功</option>
              <option value="失敗">失敗</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              ソート
            </label>
            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={(e) => {
                const [field, order] = e.target.value.split('-');
                setSortBy(field);
                setSortOrder(order);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="date-desc">日付（新しい順）</option>
              <option value="date-asc">日付（古い順）</option>
              <option value="symbol-asc">銘柄コード（昇順）</option>
              <option value="symbol-desc">銘柄コード（降順）</option>
              <option value="profit-desc">利益（高い順）</option>
              <option value="profit-asc">利益（低い順）</option>
            </select>
          </div>
        </div>
      </div>

      {/* 記録テーブル */}
      <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  銘柄
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  日付
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  投資金額
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  予想
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  結果
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  利益
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {currentRecords.map((record) => (
                <tr key={record.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div>
                      <div className="text-sm font-medium text-gray-900">{record.symbol}</div>
                      <div className="text-sm text-gray-500">{record.companyName}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {record.date}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatCurrency(record.investmentAmount)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      record.prediction === "上昇" ? "bg-green-100 text-green-800" :
                      record.prediction === "下降" ? "bg-red-100 text-red-800" :
                      "bg-gray-100 text-gray-800"
                    }`}>
                      {record.prediction === "上昇" && <TrendingUp className="h-3 w-3 mr-1" />}
                      {record.prediction === "下降" && <TrendingDown className="h-3 w-3 mr-1" />}
                      {record.prediction}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      record.result === "成功" ? "bg-green-100 text-green-800" :
                      record.result === "失敗" ? "bg-red-100 text-red-800" :
                      "bg-gray-100 text-gray-800"
                    }`}>
                      {record.result || "未確定"}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`font-medium ${
                      (record.actualProfit || 0) > 0 ? "text-green-600" :
                      (record.actualProfit || 0) < 0 ? "text-red-600" :
                      "text-gray-600"
                    }`}>
                      {record.actualProfit ? formatCurrency(record.actualProfit) : "未確定"}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex space-x-2">
                      <button
                        onClick={() => {
                          setSelectedRecord(record);
                          setShowDetailModal(true);
                        }}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(record.id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ページネーション */}
        {totalPages > 1 && (
          <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
            <div className="flex-1 flex justify-between sm:hidden">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
                className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                前へ
              </button>
              <button
                onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage === totalPages}
                className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                次へ
              </button>
            </div>
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  <span className="font-medium">{startIndex + 1}</span>
                  {" - "}
                  <span className="font-medium">{Math.min(endIndex, filteredRecords.length)}</span>
                  {" / "}
                  <span className="font-medium">{filteredRecords.length}</span>
                  件の記録
                </p>
              </div>
              <div>
                <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                  <button
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                        page === currentPage
                          ? "z-10 bg-blue-50 border-blue-500 text-blue-600"
                          : "bg-white border-gray-300 text-gray-500 hover:bg-gray-50"
                      }`}
                    >
                      {page}
                    </button>
                  ))}
                  <button
                    onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                    disabled={currentPage === totalPages}
                    className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </nav>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 詳細モーダル */}
      {showDetailModal && (
        <DetailModal
          record={selectedRecord}
          onClose={() => {
            setShowDetailModal(false);
            setSelectedRecord(null);
          }}
        />
      )}
    </div>
  );
};

export default RecordsList;
