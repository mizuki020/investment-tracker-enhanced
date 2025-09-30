import { useState, useEffect } from "react";
import { 
  Save, 
  Download, 
  Upload, 
  Trash2, 
  AlertTriangle,
  CheckCircle,
  Settings as SettingsIcon,
  Database,
  Bell,
  Shield,
  Palette
} from "lucide-react";

const Settings = () => {
  const [settings, setSettings] = useState({
    notifications: {
      emailAlerts: true,
      priceAlerts: false,
      weeklyReports: true
    },
    display: {
      theme: "light",
      currency: "JPY",
      dateFormat: "YYYY-MM-DD",
      chartType: "line"
    },
    trading: {
      defaultTimeframe: "中期（1ヶ月以内）",
      riskLevel: "medium",
      autoSave: true
    }
  });

  const [dataStats, setDataStats] = useState({
    totalRecords: 0,
    totalSize: "0 KB",
    lastBackup: null
  });

  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");

  useEffect(() => {
    // ローカルストレージから設定を読み込み
    const savedSettings = localStorage.getItem('appSettings');
    if (savedSettings) {
      setSettings(JSON.parse(savedSettings));
    }

    // データ統計を計算
    const records = JSON.parse(localStorage.getItem('investmentRecords') || '[]');
    const dataSize = new Blob([JSON.stringify(records)]).size;
    const lastBackup = localStorage.getItem('lastBackupDate');

    setDataStats({
      totalRecords: records.length,
      totalSize: formatBytes(dataSize),
      lastBackup: lastBackup ? new Date(lastBackup).toLocaleDateString('ja-JP') : null
    });
  }, []);

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleSettingChange = (category, key, value) => {
    setSettings(prev => ({
      ...prev,
      [category]: {
        ...prev[category],
        [key]: value
      }
    }));
  };

  const saveSettings = () => {
    localStorage.setItem('appSettings', JSON.stringify(settings));
    setSaveStatus("success");
    setTimeout(() => setSaveStatus(""), 3000);
  };

  const exportData = async () => {
    setIsExporting(true);
    try {
      const records = JSON.parse(localStorage.getItem('investmentRecords') || '[]');
      const exportData = {
        records,
        settings,
        exportDate: new Date().toISOString(),
        version: "1.0"
      };

      const dataStr = JSON.stringify(exportData, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      
      const link = document.createElement('a');
      link.href = URL.createObjectURL(dataBlob);
      link.download = `investment_data_backup_${new Date().toISOString().split('T')[0]}.json`;
      link.click();

      // バックアップ日時を記録
      localStorage.setItem('lastBackupDate', new Date().toISOString());
      setDataStats(prev => ({
        ...prev,
        lastBackup: new Date().toLocaleDateString('ja-JP')
      }));

    } catch (error) {
      console.error('Export error:', error);
      alert('エクスポート中にエラーが発生しました。');
    } finally {
      setIsExporting(false);
    }
  };

  const importData = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsImporting(true);
    const reader = new FileReader();
    
    reader.onload = (e) => {
      try {
        const importedData = JSON.parse(e.target.result);
        
        if (importedData.records && Array.isArray(importedData.records)) {
          localStorage.setItem('investmentRecords', JSON.stringify(importedData.records));
        }
        
        if (importedData.settings) {
          setSettings(importedData.settings);
          localStorage.setItem('appSettings', JSON.stringify(importedData.settings));
        }

        alert('データのインポートが完了しました。ページを再読み込みしてください。');
        window.location.reload();
      } catch (error) {
        console.error('Import error:', error);
        alert('インポートファイルの形式が正しくありません。');
      } finally {
        setIsImporting(false);
      }
    };
    
    reader.readAsText(file);
  };

  const deleteAllData = () => {
    localStorage.removeItem('investmentRecords');
    localStorage.removeItem('appSettings');
    localStorage.removeItem('lastBackupDate');
    setShowDeleteConfirm(false);
    alert('すべてのデータが削除されました。ページを再読み込みします。');
    window.location.reload();
  };

  const SettingSection = ({ title, icon: Icon, children }) => (
    <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <Icon className="h-5 w-5 mr-2 text-blue-600" />
          {title}
        </h3>
      </div>
      <div className="p-6">
        {children}
      </div>
    </div>
  );

  const ToggleSwitch = ({ enabled, onChange, label, description }) => (
    <div className="flex items-center justify-between py-3">
      <div className="flex-1">
        <label className="text-sm font-medium text-gray-900">{label}</label>
        {description && (
          <p className="text-sm text-gray-500 mt-1">{description}</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onChange(!enabled)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
          enabled ? 'bg-blue-600' : 'bg-gray-200'
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
            enabled ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  );

  return (
    <div className="space-y-8">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">設定</h1>
          <p className="text-gray-600 mt-1">アプリケーションの設定とデータ管理</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={saveSettings}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200"
          >
            <Save className="h-5 w-5 mr-2" />
            設定を保存
          </button>
        </div>
      </div>

      {/* 保存ステータス */}
      {saveStatus === "success" && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center">
            <CheckCircle className="h-5 w-5 text-green-600 mr-2" />
            <span className="text-green-800">設定が正常に保存されました</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 通知設定 */}
        <SettingSection title="通知設定" icon={Bell}>
          <div className="space-y-1">
            <ToggleSwitch
              enabled={settings.notifications.emailAlerts}
              onChange={(value) => handleSettingChange('notifications', 'emailAlerts', value)}
              label="メール通知"
              description="重要な更新をメールで受け取る"
            />
            <ToggleSwitch
              enabled={settings.notifications.priceAlerts}
              onChange={(value) => handleSettingChange('notifications', 'priceAlerts', value)}
              label="価格アラート"
              description="目標価格に達した時の通知"
            />
            <ToggleSwitch
              enabled={settings.notifications.weeklyReports}
              onChange={(value) => handleSettingChange('notifications', 'weeklyReports', value)}
              label="週次レポート"
              description="週次パフォーマンスレポートを受け取る"
            />
          </div>
        </SettingSection>

        {/* 表示設定 */}
        <SettingSection title="表示設定" icon={Palette}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">テーマ</label>
              <select
                value={settings.display.theme}
                onChange={(e) => handleSettingChange('display', 'theme', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="light">ライト</option>
                <option value="dark">ダーク</option>
                <option value="auto">自動</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">通貨</label>
              <select
                value={settings.display.currency}
                onChange={(e) => handleSettingChange('display', 'currency', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="JPY">日本円 (¥)</option>
                <option value="USD">米ドル ($)</option>
                <option value="EUR">ユーロ (€)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">日付形式</label>
              <select
                value={settings.display.dateFormat}
                onChange={(e) => handleSettingChange('display', 'dateFormat', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="YYYY-MM-DD">2025-09-30</option>
                <option value="DD/MM/YYYY">30/09/2025</option>
                <option value="MM/DD/YYYY">09/30/2025</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">チャートタイプ</label>
              <select
                value={settings.display.chartType}
                onChange={(e) => handleSettingChange('display', 'chartType', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="line">ライン</option>
                <option value="bar">バー</option>
                <option value="area">エリア</option>
              </select>
            </div>
          </div>
        </SettingSection>

        {/* 取引設定 */}
        <SettingSection title="取引設定" icon={SettingsIcon}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">デフォルト投資期間</label>
              <select
                value={settings.trading.defaultTimeframe}
                onChange={(e) => handleSettingChange('trading', 'defaultTimeframe', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="短期（1週間以内）">短期（1週間以内）</option>
                <option value="中期（1ヶ月以内）">中期（1ヶ月以内）</option>
                <option value="長期（3ヶ月以上）">長期（3ヶ月以上）</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">リスクレベル</label>
              <select
                value={settings.trading.riskLevel}
                onChange={(e) => handleSettingChange('trading', 'riskLevel', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="low">低リスク</option>
                <option value="medium">中リスク</option>
                <option value="high">高リスク</option>
              </select>
            </div>

            <ToggleSwitch
              enabled={settings.trading.autoSave}
              onChange={(value) => handleSettingChange('trading', 'autoSave', value)}
              label="自動保存"
              description="入力内容を自動的に保存する"
            />
          </div>
        </SettingSection>

        {/* データ管理 */}
        <SettingSection title="データ管理" icon={Database}>
          <div className="space-y-6">
            {/* データ統計 */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-3">データ統計</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">総記録数:</span>
                  <span className="ml-2 font-medium">{dataStats.totalRecords}</span>
                </div>
                <div>
                  <span className="text-gray-600">データサイズ:</span>
                  <span className="ml-2 font-medium">{dataStats.totalSize}</span>
                </div>
                <div className="col-span-2">
                  <span className="text-gray-600">最終バックアップ:</span>
                  <span className="ml-2 font-medium">
                    {dataStats.lastBackup || "未実行"}
                  </span>
                </div>
              </div>
            </div>

            {/* データ操作 */}
            <div className="space-y-3">
              <button
                onClick={exportData}
                disabled={isExporting}
                className="w-full flex items-center justify-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors duration-200"
              >
                {isExporting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    エクスポート中...
                  </>
                ) : (
                  <>
                    <Download className="h-5 w-5 mr-2" />
                    データをエクスポート
                  </>
                )}
              </button>

              <div className="relative">
                <input
                  type="file"
                  accept=".json"
                  onChange={importData}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  disabled={isImporting}
                />
                <button
                  disabled={isImporting}
                  className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors duration-200"
                >
                  {isImporting ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      インポート中...
                    </>
                  ) : (
                    <>
                      <Upload className="h-5 w-5 mr-2" />
                      データをインポート
                    </>
                  )}
                </button>
              </div>

              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="w-full flex items-center justify-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors duration-200"
              >
                <Trash2 className="h-5 w-5 mr-2" />
                すべてのデータを削除
              </button>
            </div>
          </div>
        </SettingSection>
      </div>

      {/* 削除確認モーダル */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex items-center mb-4">
              <AlertTriangle className="h-6 w-6 text-red-600 mr-2" />
              <h3 className="text-lg font-semibold text-gray-900">データ削除の確認</h3>
            </div>
            <p className="text-gray-600 mb-6">
              すべての投資記録と設定が完全に削除されます。この操作は取り消すことができません。
              本当に削除しますか？
            </p>
            <div className="flex space-x-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                キャンセル
              </button>
              <button
                onClick={deleteAllData}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                削除する
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
