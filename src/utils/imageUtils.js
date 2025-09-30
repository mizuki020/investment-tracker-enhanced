import imageCompression from 'browser-image-compression';

// 画像処理ユーティリティ関数

// ファイルを Base64 に変換
export const fileToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result);
    reader.onerror = error => reject(error);
  });
};

// 画像を圧縮
export const compressImage = async (file, options = {}) => {
  const defaultOptions = {
    maxSizeMB: 1,
    maxWidthOrHeight: 1920,
    useWebWorker: true,
    fileType: file.type
  };

  const compressionOptions = { ...defaultOptions, ...options };

  try {
    const compressedFile = await imageCompression(file, compressionOptions);
    return compressedFile;
  } catch (error) {
    console.error('画像圧縮エラー:', error);
    throw error;
  }
};

// サムネイルを生成
export const generateThumbnail = (file, maxSize = 200) => {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
      // アスペクト比を維持してサイズを計算
      let { width, height } = img;
      if (width > height) {
        if (width > maxSize) {
          height = (height * maxSize) / width;
          width = maxSize;
        }
      } else {
        if (height > maxSize) {
          width = (width * maxSize) / height;
          height = maxSize;
        }
      }

      canvas.width = width;
      canvas.height = height;

      // 画像を描画
      ctx.drawImage(img, 0, 0, width, height);

      // Base64として出力
      const thumbnailDataUrl = canvas.toDataURL('image/jpeg', 0.8);
      resolve(thumbnailDataUrl);
    };

    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
};

// 画像のメタデータを取得
export const getImageMetadata = (file) => {
  return new Promise((resolve, reject) => {
    const img = new Image();
    
    img.onload = () => {
      const metadata = {
        width: img.naturalWidth,
        height: img.naturalHeight,
        aspectRatio: img.naturalWidth / img.naturalHeight,
        fileName: file.name,
        fileSize: file.size,
        mimeType: file.type,
        lastModified: file.lastModified
      };
      resolve(metadata);
    };

    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
};

// ファイル形式を検証
export const validateImageFile = (file) => {
  const allowedTypes = [
    'image/jpeg',
    'image/jpg', 
    'image/png',
    'image/gif',
    'image/webp',
    'image/svg+xml'
  ];

  const maxSize = 10 * 1024 * 1024; // 10MB

  if (!allowedTypes.includes(file.type)) {
    return {
      isValid: false,
      error: `サポートされていないファイル形式です。対応形式: ${allowedTypes.join(', ')}`
    };
  }

  if (file.size > maxSize) {
    return {
      isValid: false,
      error: `ファイルサイズが大きすぎます。最大サイズ: ${maxSize / (1024 * 1024)}MB`
    };
  }

  return { isValid: true };
};

// 複数ファイルを検証
export const validateMultipleFiles = (files, maxCount = 20) => {
  if (files.length > maxCount) {
    return {
      isValid: false,
      error: `一度にアップロードできる画像数は最大${maxCount}枚です。`
    };
  }

  const invalidFiles = [];
  files.forEach((file, index) => {
    const validation = validateImageFile(file);
    if (!validation.isValid) {
      invalidFiles.push({ index, name: file.name, error: validation.error });
    }
  });

  if (invalidFiles.length > 0) {
    return {
      isValid: false,
      error: '一部のファイルが無効です。',
      invalidFiles
    };
  }

  return { isValid: true };
};

// 画像を処理（圧縮 + サムネイル生成）
export const processImage = async (file, options = {}) => {
  try {
    // メタデータを取得
    const metadata = await getImageMetadata(file);
    
    // 画像を圧縮
    const compressedFile = await compressImage(file, options.compression);
    const compressedBase64 = await fileToBase64(compressedFile);
    
    // サムネイルを生成
    const thumbnail = await generateThumbnail(file, options.thumbnailSize || 200);
    
    return {
      originalName: file.name,
      fileName: `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      fileSize: compressedFile.size,
      mimeType: compressedFile.type,
      compressed: compressedBase64,
      thumbnail: thumbnail,
      width: metadata.width,
      height: metadata.height,
      aspectRatio: metadata.aspectRatio
    };
  } catch (error) {
    console.error('画像処理エラー:', error);
    throw error;
  }
};

// 複数画像を並列処理
export const processMultipleImages = async (files, options = {}, onProgress = null) => {
  const results = [];
  const errors = [];

  for (let i = 0; i < files.length; i++) {
    try {
      const processedImage = await processImage(files[i], options);
      results.push(processedImage);
      
      if (onProgress) {
        onProgress({
          completed: i + 1,
          total: files.length,
          percentage: Math.round(((i + 1) / files.length) * 100)
        });
      }
    } catch (error) {
      errors.push({
        file: files[i].name,
        error: error.message
      });
    }
  }

  return { results, errors };
};

// ファイルサイズを人間が読みやすい形式に変換
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// 画像の向きを修正（EXIF情報に基づく）
export const correctImageOrientation = (file) => {
  return new Promise((resolve) => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);
      
      canvas.toBlob((blob) => {
        const correctedFile = new File([blob], file.name, {
          type: file.type,
          lastModified: Date.now()
        });
        resolve(correctedFile);
      }, file.type, 0.9);
    };

    img.src = URL.createObjectURL(file);
  });
};

// 画像をリサイズ
export const resizeImage = (file, maxWidth, maxHeight, quality = 0.9) => {
  return new Promise((resolve) => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
      let { width, height } = img;

      // アスペクト比を維持してリサイズ
      if (width > height) {
        if (width > maxWidth) {
          height = (height * maxWidth) / width;
          width = maxWidth;
        }
      } else {
        if (height > maxHeight) {
          width = (width * maxHeight) / height;
          height = maxHeight;
        }
      }

      canvas.width = width;
      canvas.height = height;
      ctx.drawImage(img, 0, 0, width, height);

      canvas.toBlob((blob) => {
        const resizedFile = new File([blob], file.name, {
          type: file.type,
          lastModified: Date.now()
        });
        resolve(resizedFile);
      }, file.type, quality);
    };

    img.src = URL.createObjectURL(file);
  });
};

// Base64からBlobに変換
export const base64ToBlob = (base64, mimeType) => {
  const byteCharacters = atob(base64.split(',')[1]);
  const byteNumbers = new Array(byteCharacters.length);
  
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: mimeType });
};

// 画像をダウンロード
export const downloadImage = (base64Data, fileName) => {
  const link = document.createElement('a');
  link.href = base64Data;
  link.download = fileName;
  link.click();
};
