import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { 
  Save, 
  Upload, 
  X, 
  Calendar, 
  DollarSign, 
  TrendingUp, 
  TrendingDown,
  FileImage,
  AlertCircle
} from "lucide-react";

const InvestmentForm = () => {
  const [formData, setFormData] = useState({
    symbol: "",
    companyName: "",
    date: new Date().toISOString().split('T')[0],
    investmentAmount: "",
    prediction: "",
    predictionReason: "",
    targetPrice: "",
    stopLoss: "",
    timeframe: "",
    analysis: "",
    chartImages: []
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ドラッグ&ドロップ機能
  const onDrop = useCallback((acceptedFiles) => {
    const imageFiles = acceptedFiles.filter(file => file.type.startsWith('image/'));
    
    imageFiles.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        setFormData(prev => ({
          ...prev,
          chartImages: [...prev.chartImages, {
            id: Date.now() + Math.random(),
            file: file,
            preview: e.target.result,
            name: file.name
          }]
        }));
      };
      reader.readAsDataURL(file);
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.webp']
    },
    multiple: true
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    // エラーをクリア
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ""
      }));
    }
  };

  const removeImage = (imageId) => {
    setFormData(prev => ({
      ...prev,
      chartImages: prev.chartImages.filter(img => img.id !== imageId)
    }));
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.symbol.trim()) {
      newErrors.symbol = "銘柄コードは必須です";
    }
    if (!formData.companyName.trim()) {
      newErrors.companyName = "企業名は必須です";
    }
    if (!formData.date) {
      newErrors.date = "日付は必須です";
    }
    if (!formData.investmentAmount || parseFloat(formData.investmentAmount) <= 0) {
      newErrors.investmentAmount = "有効な投資金額を入力してください";
    }
    if (!formData.prediction) {
      newErrors.prediction = "予想を選択してください";
    }
    if (!formData.analysis.trim()) {
      newErrors.analysis = "分析内容は必須です";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      // ここで実際のデータ保存処理を行う
      // 現在はローカルストレージに保存
      const existingRecords = JSON.parse(localStorage.getItem('investmentRecords') || '[]');
      const newRecord = {
        id: Date.now(),
        ...formData,
        createdAt: new Date().toISOString()
      };
      
      existingRecords.push(newRecord);
      localStorage.setItem('investmentRecords', JSON.stringify(existingRecords));

      // フォームをリセット
      setFormData({
        symbol: "",
        companyName: "",
        date: new Date().toISOString().split('T')[0],
        investmentAmount: "",
        prediction: "",
        predictionReason: "",
        targetPrice: "",
        stopLoss: "",
        timeframe: "",
        analysis: "",
        chartImages: []
      });

      alert("投資記録が正常に保存されました！");
    } catch (error) {
      console.error("保存エラー:", error);
      alert("保存中にエラーが発生しました。もう一度お試しください。");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-md border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h1 className="text-2xl font-bold text-gray-900">新しい投資記録を追加</h1>
          <p className="text-gray-600 mt-1">投資判断と分析を記録して、将来の参考にしましょう</p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* 基本情報 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                銘柄コード *
              </label>
              <input
                type="text"
                name="symbol"
                value={formData.symbol}
                onChange={handleInputChange}
                placeholder="例: 7203"
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.symbol ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.symbol && (
                <p className="mt-1 text-sm text-red-600 flex items-center">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.symbol}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                企業名 *
              </label>
              <input
                type="text"
                name="companyName"
                value={formData.companyName}
                onChange={handleInputChange}
                placeholder="例: トヨタ自動車"
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.companyName ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.companyName && (
                <p className="mt-1 text-sm text-red-600 flex items-center">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.companyName}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <Calendar className="inline h-4 w-4 mr-1" />
                投資日 *
              </label>
              <input
                type="date"
                name="date"
                value={formData.date}
                onChange={handleInputChange}
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.date ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.date && (
                <p className="mt-1 text-sm text-red-600 flex items-center">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.date}
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <DollarSign className="inline h-4 w-4 mr-1" />
                投資金額 *
              </label>
              <input
                type="number"
                name="investmentAmount"
                value={formData.investmentAmount}
                onChange={handleInputChange}
                placeholder="例: 100000"
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  errors.investmentAmount ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {errors.investmentAmount && (
                <p className="mt-1 text-sm text-red-600 flex items-center">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  {errors.investmentAmount}
                </p>
              )}
            </div>
          </div>

          {/* 予想情報 */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">予想・戦略</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  価格予想 *
                </label>
                <select
                  name="prediction"
                  value={formData.prediction}
                  onChange={handleInputChange}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    errors.prediction ? 'border-red-500' : 'border-gray-300'
                  }`}
                >
                  <option value="">選択してください</option>
                  <option value="上昇">上昇</option>
                  <option value="下降">下降</option>
                  <option value="横ばい">横ばい</option>
                </select>
                {errors.prediction && (
                  <p className="mt-1 text-sm text-red-600 flex items-center">
                    <AlertCircle className="h-4 w-4 mr-1" />
                    {errors.prediction}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  目標価格
                </label>
                <input
                  type="number"
                  name="targetPrice"
                  value={formData.targetPrice}
                  onChange={handleInputChange}
                  placeholder="例: 2500"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  ストップロス
                </label>
                <input
                  type="number"
                  name="stopLoss"
                  value={formData.stopLoss}
                  onChange={handleInputChange}
                  placeholder="例: 2000"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  投資期間
                </label>
                <select
                  name="timeframe"
                  value={formData.timeframe}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">選択してください</option>
                  <option value="短期（1週間以内）">短期（1週間以内）</option>
                  <option value="中期（1ヶ月以内）">中期（1ヶ月以内）</option>
                  <option value="長期（3ヶ月以上）">長期（3ヶ月以上）</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  予想根拠
                </label>
                <input
                  type="text"
                  name="predictionReason"
                  value={formData.predictionReason}
                  onChange={handleInputChange}
                  placeholder="例: 決算好調、新製品発表"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {/* チャート画像アップロード */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">チャート画像</h3>
            
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                isDragActive 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <input {...getInputProps()} />
              <FileImage className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              {isDragActive ? (
                <p className="text-blue-600">ファイルをドロップしてください...</p>
              ) : (
                <div>
                  <p className="text-gray-600 mb-2">
                    チャート画像をドラッグ&ドロップするか、クリックして選択
                  </p>
                  <p className="text-sm text-gray-500">
                    PNG, JPG, GIF, WebP形式をサポート
                  </p>
                </div>
              )}
            </div>

            {/* アップロードされた画像のプレビュー */}
            {formData.chartImages.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {formData.chartImages.map((image) => (
                  <div key={image.id} className="relative group">
                    <img
                      src={image.preview}
                      alt={image.name}
                      className="w-full h-32 object-cover rounded-lg border border-gray-200"
                    />
                    <button
                      type="button"
                      onClick={() => removeImage(image.id)}
                      className="absolute top-2 right-2 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X className="h-4 w-4" />
                    </button>
                    <p className="text-xs text-gray-500 mt-1 truncate">{image.name}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 分析内容 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              分析・メモ *
            </label>
            <textarea
              name="analysis"
              value={formData.analysis}
              onChange={handleInputChange}
              rows={6}
              placeholder="投資判断の根拠、テクニカル分析、ファンダメンタル分析、市場環境などを詳しく記録してください..."
              className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.analysis ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {errors.analysis && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertCircle className="h-4 w-4 mr-1" />
                {errors.analysis}
              </p>
            )}
          </div>

          {/* 送信ボタン */}
          <div className="flex justify-end space-x-4 pt-6 border-t border-gray-200">
            <button
              type="button"
              className="px-6 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition-colors"
              onClick={() => {
                if (confirm("入力内容をクリアしますか？")) {
                  setFormData({
                    symbol: "",
                    companyName: "",
                    date: new Date().toISOString().split('T')[0],
                    investmentAmount: "",
                    prediction: "",
                    predictionReason: "",
                    targetPrice: "",
                    stopLoss: "",
                    timeframe: "",
                    analysis: "",
                    chartImages: []
                  });
                  setErrors({});
                }
              }}
            >
              クリア
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center"
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  保存中...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  記録を保存
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default InvestmentForm;
