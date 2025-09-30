import { useState, useEffect, useCallback } from "react";
import { 
  Search, 
  Filter, 
  Grid, 
  List, 
  Eye, 
  Download, 
  Trash2, 
  Edit3,
  Tag,
  Folder,
  Calendar,
  FileImage,
  X,
  Check,
  MoreVertical,
  SortAsc,
  SortDesc
} from "lucide-react";
import imageDB from "../utils/imageDatabase";
import { formatFileSize, downloadImage } from "../utils/imageUtils";

const ImageLibrary = () => {
  const [images, setImages] = useState([]);
  const [filteredImages, setFilteredImages] = useState([]);
  const [categories, setCategories] = useState([]);
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'
  const [selectedImages, setSelectedImages] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedTag, setSelectedTag] = useState('all');
  const [sortBy, setSortBy] = useState('uploadDate');
  const [sortOrder, setSortOrder] = useState('desc');
  const [stats, setStats] = useState({});

  // データを読み込み
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [imagesData, categoriesData, tagsData, statsData] = await Promise.all([
        imageDB.getAllImages(),
        imageDB.getAllCategories(),
        imageDB.getAllTags(),
        imageDB.getDatabaseStats()
      ]);
      
      setImages(imagesData);
      setCategories(categoriesData);
      setTags(tagsData);
      setStats(statsData);
    } catch (error) {
      console.error('データ読み込みエラー:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // 初期化
  useEffect(() => {
    loadData();
  }, [loadData]);

  // フィルタリングとソート
  useEffect(() => {
    let filtered = [...images];

    // 検索フィルター
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(image => 
        image.originalName.toLowerCase().includes(query) ||
        image.category.toLowerCase().includes(query) ||
        image.tags.some(tag => tag.toLowerCase().includes(query))
      );
    }

    // カテゴリフィルター
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(image => image.category === selectedCategory);
    }

    // タグフィルター
    if (selectedTag !== 'all') {
      filtered = filtered.filter(image => image.tags.includes(selectedTag));
    }

    // ソート
    filtered.sort((a, b) => {
      let aValue, bValue;
      
      switch (sortBy) {
        case 'uploadDate':
          aValue = new Date(a.uploadDate);
          bValue = new Date(b.uploadDate);
          break;
        case 'fileName':
          aValue = a.originalName.toLowerCase();
          bValue = b.originalName.toLowerCase();
          break;
        case 'fileSize':
          aValue = a.fileSize;
          bValue = b.fileSize;
          break;
        case 'category':
          aValue = a.category.toLowerCase();
          bValue = b.category.toLowerCase();
          break;
        default:
          aValue = a[sortBy];
          bValue = b[sortBy];
      }

      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    setFilteredImages(filtered);
  }, [images, searchQuery, selectedCategory, selectedTag, sortBy, sortOrder]);

  // 画像選択の切り替え
  const toggleImageSelection = (imageId) => {
    setSelectedImages(prev => 
      prev.includes(imageId) 
        ? prev.filter(id => id !== imageId)
        : [...prev, imageId]
    );
  };

  // 全選択/全解除
  const toggleSelectAll = () => {
    if (selectedImages.length === filteredImages.length) {
      setSelectedImages([]);
    } else {
      setSelectedImages(filteredImages.map(img => img.id));
    }
  };

  // 選択された画像を削除
  const deleteSelectedImages = async () => {
    if (selectedImages.length === 0) return;
    
    if (confirm(`選択された${selectedImages.length}枚の画像を削除しますか？`)) {
      try {
        await imageDB.deleteMultipleImages(selectedImages);
        await loadData();
        setSelectedImages([]);
      } catch (error) {
        console.error('画像削除エラー:', error);
        alert('画像の削除中にエラーが発生しました。');
      }
    }
  };

  // 画像を削除
  const deleteImage = async (imageId) => {
    if (confirm('この画像を削除しますか？')) {
      try {
        await imageDB.deleteImage(imageId);
        await loadData();
      } catch (error) {
        console.error('画像削除エラー:', error);
        alert('画像の削除中にエラーが発生しました。');
      }
    }
  };

  // プレビューを表示
  const showImagePreview = (image) => {
    setPreviewImage(image);
    setShowPreview(true);
  };

  // 画像をダウンロード
  const handleDownloadImage = (image) => {
    downloadImage(image.compressed, image.originalName);
  };

  // 複数画像をダウンロード
  const downloadSelectedImages = async () => {
    if (selectedImages.length === 0) return;
    
    for (const imageId of selectedImages) {
      const image = images.find(img => img.id === imageId);
      if (image) {
        handleDownloadImage(image);
        // ダウンロード間隔を空ける
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">画像を読み込み中...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">画像ライブラリ</h1>
          <p className="text-gray-600 mt-1">
            投資記録に関連する画像を管理・整理できます
          </p>
        </div>
        
        {/* 統計情報 */}
        <div className="flex items-center space-x-4 text-sm text-gray-600">
          <span>総画像数: {stats.totalImages}</span>
          <span>総サイズ: {formatFileSize(stats.totalSize)}</span>
        </div>
      </div>

      {/* フィルター・検索バー */}
      <div className="bg-white rounded-lg shadow-md border border-gray-200 p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          {/* 検索 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="画像を検索..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* カテゴリフィルター */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">すべてのカテゴリ</option>
            {categories.map(category => (
              <option key={category.id} value={category.name}>
                {category.name}
              </option>
            ))}
          </select>

          {/* タグフィルター */}
          <select
            value={selectedTag}
            onChange={(e) => setSelectedTag(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">すべてのタグ</option>
            {tags.map(tag => (
              <option key={tag.id} value={tag.name}>
                {tag.name}
              </option>
            ))}
          </select>

          {/* ソート */}
          <div className="flex">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="uploadDate">アップロード日</option>
              <option value="fileName">ファイル名</option>
              <option value="fileSize">ファイルサイズ</option>
              <option value="category">カテゴリ</option>
            </select>
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="px-3 py-2 border border-l-0 border-gray-300 rounded-r-md hover:bg-gray-50 transition-colors"
            >
              {sortOrder === 'asc' ? <SortAsc className="h-4 w-4" /> : <SortDesc className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* アクションバー */}
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <button
              onClick={toggleSelectAll}
              className="flex items-center px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
            >
              <Check className="h-4 w-4 mr-1" />
              {selectedImages.length === filteredImages.length ? '全解除' : '全選択'}
            </button>
            
            {selectedImages.length > 0 && (
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600">
                  {selectedImages.length}枚選択中
                </span>
                <button
                  onClick={downloadSelectedImages}
                  className="flex items-center px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  <Download className="h-4 w-4 mr-1" />
                  ダウンロード
                </button>
                <button
                  onClick={deleteSelectedImages}
                  className="flex items-center px-3 py-1 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  削除
                </button>
              </div>
            )}
          </div>

          {/* 表示モード切り替え */}
          <div className="flex items-center space-x-1 border border-gray-300 rounded-md">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 ${viewMode === 'grid' ? 'bg-blue-100 text-blue-600' : 'text-gray-600 hover:bg-gray-100'} transition-colors`}
            >
              <Grid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 ${viewMode === 'list' ? 'bg-blue-100 text-blue-600' : 'text-gray-600 hover:bg-gray-100'} transition-colors`}
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 画像一覧 */}
      {filteredImages.length === 0 ? (
        <div className="bg-white rounded-lg shadow-md border border-gray-200 p-12 text-center">
          <FileImage className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">画像が見つかりません</h3>
          <p className="text-gray-600">
            {searchQuery || selectedCategory !== 'all' || selectedTag !== 'all' 
              ? 'フィルター条件に一致する画像がありません。' 
              : 'まだ画像がアップロードされていません。'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-md border border-gray-200">
          {viewMode === 'grid' ? (
            // グリッド表示
            <div className="p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {filteredImages.map((image) => (
                  <div
                    key={image.id}
                    className={`relative group border-2 rounded-lg overflow-hidden transition-all ${
                      selectedImages.includes(image.id)
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    {/* 選択チェックボックス */}
                    <input
                      type="checkbox"
                      checked={selectedImages.includes(image.id)}
                      onChange={() => toggleImageSelection(image.id)}
                      className="absolute top-2 left-2 z-10 w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />

                    {/* 画像サムネイル */}
                    <div className="aspect-square bg-gray-100 flex items-center justify-center">
                      <img
                        src={image.thumbnail}
                        alt={image.originalName}
                        className="w-full h-full object-cover cursor-pointer"
                        onClick={() => showImagePreview(image)}
                      />
                    </div>

                    {/* 画像情報 */}
                    <div className="p-2 bg-white">
                      <p className="text-xs font-medium text-gray-900 truncate">
                        {image.originalName}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatFileSize(image.fileSize)}
                      </p>
                      <div className="flex items-center mt-1">
                        <span 
                          className="inline-block w-2 h-2 rounded-full mr-1"
                          style={{ backgroundColor: categories.find(c => c.name === image.category)?.color || '#6B7280' }}
                        />
                        <span className="text-xs text-gray-500 truncate">
                          {image.category}
                        </span>
                      </div>
                    </div>

                    {/* ホバー時のアクション */}
                    <div className="absolute inset-0 bg-black bg-opacity-50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center space-x-2">
                      <button
                        onClick={() => showImagePreview(image)}
                        className="p-2 bg-white text-gray-700 rounded-full hover:bg-gray-100 transition-colors"
                        title="プレビュー"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDownloadImage(image)}
                        className="p-2 bg-white text-gray-700 rounded-full hover:bg-gray-100 transition-colors"
                        title="ダウンロード"
                      >
                        <Download className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => deleteImage(image.id)}
                        className="p-2 bg-white text-red-600 rounded-full hover:bg-red-50 transition-colors"
                        title="削除"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            // リスト表示
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <input
                        type="checkbox"
                        checked={selectedImages.length === filteredImages.length}
                        onChange={toggleSelectAll}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      画像
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      ファイル名
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      カテゴリ
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      サイズ
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      アップロード日
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      アクション
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredImages.map((image) => (
                    <tr key={image.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={selectedImages.includes(image.id)}
                          onChange={() => toggleImageSelection(image.id)}
                          className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                        />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <img
                          src={image.thumbnail}
                          alt={image.originalName}
                          className="w-12 h-12 object-cover rounded cursor-pointer"
                          onClick={() => showImagePreview(image)}
                        />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {image.originalName}
                        </div>
                        <div className="text-sm text-gray-500">
                          {image.width} × {image.height}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <span 
                            className="inline-block w-2 h-2 rounded-full mr-2"
                            style={{ backgroundColor: categories.find(c => c.name === image.category)?.color || '#6B7280' }}
                          />
                          <span className="text-sm text-gray-900">{image.category}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatFileSize(image.fileSize)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(image.uploadDate).toLocaleDateString('ja-JP')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => showImagePreview(image)}
                            className="text-blue-600 hover:text-blue-900 transition-colors"
                            title="プレビュー"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDownloadImage(image)}
                            className="text-green-600 hover:text-green-900 transition-colors"
                            title="ダウンロード"
                          >
                            <Download className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => deleteImage(image.id)}
                            className="text-red-600 hover:text-red-900 transition-colors"
                            title="削除"
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
          )}
        </div>
      )}

      {/* プレビューモーダル */}
      {showPreview && previewImage && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl max-h-full overflow-auto">
            <div className="flex justify-between items-center p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                {previewImage.originalName}
              </h3>
              <button
                onClick={() => setShowPreview(false)}
                className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            <div className="p-4">
              <img
                src={previewImage.compressed}
                alt={previewImage.originalName}
                className="max-w-full max-h-96 mx-auto"
              />
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p><strong>ファイル名:</strong> {previewImage.originalName}</p>
                  <p><strong>サイズ:</strong> {formatFileSize(previewImage.fileSize)}</p>
                  <p><strong>形式:</strong> {previewImage.mimeType}</p>
                  <p><strong>解像度:</strong> {previewImage.width} × {previewImage.height}</p>
                </div>
                <div>
                  <p><strong>カテゴリ:</strong> {previewImage.category}</p>
                  <p><strong>タグ:</strong> {previewImage.tags.join(', ') || 'なし'}</p>
                  <p><strong>アップロード日:</strong> {new Date(previewImage.uploadDate).toLocaleDateString('ja-JP')}</p>
                </div>
              </div>
              <div className="mt-4 flex justify-end space-x-2">
                <button
                  onClick={() => handleDownloadImage(previewImage)}
                  className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  <Download className="h-4 w-4 mr-2" />
                  ダウンロード
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageLibrary;
