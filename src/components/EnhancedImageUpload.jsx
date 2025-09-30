import { useState, useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { 
  Upload, 
  X, 
  Image as ImageIcon, 
  FileImage, 
  AlertCircle, 
  CheckCircle,
  RotateCw,
  Crop,
  Download,
  Tag,
  Folder,
  Eye,
  Trash2,
  Plus
} from "lucide-react";
import imageDB from "../utils/imageDatabase";
import { 
  validateMultipleFiles, 
  processMultipleImages, 
  formatFileSize,
  downloadImage
} from "../utils/imageUtils";

const EnhancedImageUpload = ({ 
  onImagesUploaded, 
  recordId = null, 
  maxFiles = 20,
  showLibrary = true 
}) => {
  const [uploadedImages, setUploadedImages] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errors, setErrors] = useState([]);
  const [selectedImages, setSelectedImages] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);
  const [categories, setCategories] = useState([]);
  const [tags, setTags] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('uncategorized');
  const [selectedTags, setSelectedTags] = useState([]);
  const [newTag, setNewTag] = useState('');

  // カテゴリとタグを読み込み
  const loadCategoriesAndTags = useCallback(async () => {
    try {
      const [categoriesData, tagsData] = await Promise.all([
        imageDB.getAllCategories(),
        imageDB.getAllTags()
      ]);
      setCategories(categoriesData);
      setTags(tagsData);
    } catch (error) {
      console.error('カテゴリ・タグ読み込みエラー:', error);
    }
  }, []);

  // 初期化
  useState(() => {
    loadCategoriesAndTags();
  }, [loadCategoriesAndTags]);

  // ドロップゾーンの設定
  const onDrop = useCallback(async (acceptedFiles) => {
    setErrors([]);
    
    // ファイル検証
    const validation = validateMultipleFiles(acceptedFiles, maxFiles);
    if (!validation.isValid) {
      setErrors([validation.error]);
      if (validation.invalidFiles) {
        setErrors(prev => [...prev, ...validation.invalidFiles.map(f => f.error)]);
      }
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      // 画像を並列処理
      const { results, errors: processErrors } = await processMultipleImages(
        acceptedFiles,
        {
          compression: { maxSizeMB: 1, maxWidthOrHeight: 1920 },
          thumbnailSize: 200
        },
        (progress) => {
          setUploadProgress(progress.percentage);
        }
      );

      if (processErrors.length > 0) {
        setErrors(processErrors.map(e => `${e.file}: ${e.error}`));
      }

      // データベースに保存
      const imagesToSave = results.map(result => ({
        ...result,
        category: selectedCategory,
        tags: selectedTags,
        recordId: recordId
      }));

      const savedIds = await imageDB.saveMultipleImages(imagesToSave);
      
      // 保存された画像を取得
      const savedImages = await Promise.all(
        savedIds.map(id => imageDB.getImage(id))
      );

      setUploadedImages(prev => [...prev, ...savedImages]);
      
      if (onImagesUploaded) {
        onImagesUploaded(savedImages);
      }

    } catch (error) {
      setErrors([`アップロードエラー: ${error.message}`]);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  }, [maxFiles, selectedCategory, selectedTags, recordId, onImagesUploaded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']
    },
    multiple: true,
    maxFiles
  });

  // 画像を削除
  const handleDeleteImage = async (imageId) => {
    try {
      await imageDB.deleteImage(imageId);
      setUploadedImages(prev => prev.filter(img => img.id !== imageId));
    } catch (error) {
      setErrors([`削除エラー: ${error.message}`]);
    }
  };

  // 選択された画像を削除
  const handleDeleteSelected = async () => {
    try {
      await imageDB.deleteMultipleImages(selectedImages);
      setUploadedImages(prev => prev.filter(img => !selectedImages.includes(img.id)));
      setSelectedImages([]);
    } catch (error) {
      setErrors([`一括削除エラー: ${error.message}`]);
    }
  };

  // 画像選択の切り替え
  const toggleImageSelection = (imageId) => {
    setSelectedImages(prev => 
      prev.includes(imageId) 
        ? prev.filter(id => id !== imageId)
        : [...prev, imageId]
    );
  };

  // プレビューを表示
  const showImagePreview = (image) => {
    setPreviewImage(image);
    setShowPreview(true);
  };

  // 新しいタグを追加
  const handleAddTag = async () => {
    if (newTag.trim() && !tags.some(tag => tag.name === newTag.trim())) {
      try {
        const tagId = await imageDB.saveTag({
          name: newTag.trim(),
          color: `#${Math.floor(Math.random()*16777215).toString(16)}`
        });
        const newTagData = await imageDB.tags.get(tagId);
        setTags(prev => [...prev, newTagData]);
        setNewTag('');
      } catch (error) {
        setErrors([`タグ追加エラー: ${error.message}`]);
      }
    }
  };

  // タグ選択の切り替え
  const toggleTagSelection = (tagName) => {
    setSelectedTags(prev => 
      prev.includes(tagName)
        ? prev.filter(name => name !== tagName)
        : [...prev, tagName]
    );
  };

  return (
    <div className="space-y-6">
      {/* アップロード設定 */}
      <div className="bg-white rounded-lg shadow-md border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Upload className="h-5 w-5 mr-2 text-blue-600" />
          画像アップロード設定
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* カテゴリ選択 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Folder className="h-4 w-4 inline mr-1" />
              カテゴリ
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="uncategorized">未分類</option>
              {categories.map(category => (
                <option key={category.id} value={category.name}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>

          {/* タグ選択 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Tag className="h-4 w-4 inline mr-1" />
              タグ
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {tags.map(tag => (
                <button
                  key={tag.id}
                  onClick={() => toggleTagSelection(tag.name)}
                  className={`px-2 py-1 text-xs rounded-full border transition-colors ${
                    selectedTags.includes(tag.name)
                      ? 'bg-blue-100 border-blue-300 text-blue-800'
                      : 'bg-gray-100 border-gray-300 text-gray-700 hover:bg-gray-200'
                  }`}
                  style={{ borderColor: tag.color }}
                >
                  {tag.name}
                </button>
              ))}
            </div>
            <div className="flex">
              <input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                placeholder="新しいタグ"
                className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
              />
              <button
                onClick={handleAddTag}
                className="px-3 py-1 bg-blue-600 text-white rounded-r-md hover:bg-blue-700 transition-colors"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ドロップゾーン */}
      <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
        <div
          {...getRootProps()}
          className={`p-8 text-center cursor-pointer transition-colors ${
            isDragActive 
              ? 'bg-blue-50 border-blue-300' 
              : 'bg-gray-50 hover:bg-gray-100'
          }`}
        >
          <input {...getInputProps()} />
          <div className="flex flex-col items-center">
            <FileImage className="h-12 w-12 text-gray-400 mb-4" />
            {isDragActive ? (
              <p className="text-blue-600 font-medium">ここに画像をドロップしてください</p>
            ) : (
              <>
                <p className="text-gray-600 font-medium mb-2">
                  画像をドラッグ&ドロップまたはクリックして選択
                </p>
                <p className="text-sm text-gray-500">
                  PNG、JPG、GIF、WebP、SVG対応（最大{maxFiles}枚、各10MB以下）
                </p>
              </>
            )}
          </div>
        </div>

        {/* アップロード進捗 */}
        {isUploading && (
          <div className="px-6 py-4 bg-blue-50 border-t border-blue-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-900">
                アップロード中...
              </span>
              <span className="text-sm text-blue-700">{uploadProgress}%</span>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* エラー表示 */}
      {errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center mb-2">
            <AlertCircle className="h-5 w-5 text-red-600 mr-2" />
            <h4 className="text-red-800 font-medium">エラーが発生しました</h4>
          </div>
          <ul className="text-sm text-red-700 space-y-1">
            {errors.map((error, index) => (
              <li key={index}>• {error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* アップロード済み画像一覧 */}
      {uploadedImages.length > 0 && (
        <div className="bg-white rounded-lg shadow-md border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center">
              <ImageIcon className="h-5 w-5 mr-2 text-green-600" />
              アップロード済み画像 ({uploadedImages.length})
            </h3>
            {selectedImages.length > 0 && (
              <button
                onClick={handleDeleteSelected}
                className="flex items-center px-3 py-1 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm"
              >
                <Trash2 className="h-4 w-4 mr-1" />
                選択削除 ({selectedImages.length})
              </button>
            )}
          </div>
          
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {uploadedImages.map((image) => (
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
                    <p className="text-xs text-gray-500">
                      {image.width} × {image.height}
                    </p>
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
                      onClick={() => downloadImage(image.compressed, image.originalName)}
                      className="p-2 bg-white text-gray-700 rounded-full hover:bg-gray-100 transition-colors"
                      title="ダウンロード"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteImage(image.id)}
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
                </div>
                <div>
                  <p><strong>解像度:</strong> {previewImage.width} × {previewImage.height}</p>
                  <p><strong>カテゴリ:</strong> {previewImage.category}</p>
                  <p><strong>タグ:</strong> {previewImage.tags.join(', ') || 'なし'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EnhancedImageUpload;
