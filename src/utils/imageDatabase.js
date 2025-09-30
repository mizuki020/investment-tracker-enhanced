import Dexie from 'dexie';

// IndexedDBを使用した画像データベース管理クラス
class ImageDatabase extends Dexie {
  constructor() {
    super('InvestmentImageDB');
    
    this.version(1).stores({
      images: '++id, fileName, originalName, fileSize, mimeType, category, tags, uploadDate, recordId, compressed, thumbnail',
      categories: '++id, name, description, color',
      tags: '++id, name, color'
    });
  }

  // 画像を保存
  async saveImage(imageData) {
    try {
      const id = await this.images.add({
        fileName: imageData.fileName,
        originalName: imageData.originalName,
        fileSize: imageData.fileSize,
        mimeType: imageData.mimeType,
        category: imageData.category || 'uncategorized',
        tags: imageData.tags || [],
        uploadDate: new Date(),
        recordId: imageData.recordId || null,
        compressed: imageData.compressed, // 圧縮された画像データ（Base64）
        thumbnail: imageData.thumbnail,   // サムネイル画像データ（Base64）
        width: imageData.width,
        height: imageData.height
      });
      
      return id;
    } catch (error) {
      console.error('画像保存エラー:', error);
      throw error;
    }
  }

  // 複数画像を一括保存
  async saveMultipleImages(imagesData) {
    try {
      const ids = await this.images.bulkAdd(imagesData.map(imageData => ({
        fileName: imageData.fileName,
        originalName: imageData.originalName,
        fileSize: imageData.fileSize,
        mimeType: imageData.mimeType,
        category: imageData.category || 'uncategorized',
        tags: imageData.tags || [],
        uploadDate: new Date(),
        recordId: imageData.recordId || null,
        compressed: imageData.compressed,
        thumbnail: imageData.thumbnail,
        width: imageData.width,
        height: imageData.height
      })));
      
      return ids;
    } catch (error) {
      console.error('複数画像保存エラー:', error);
      throw error;
    }
  }

  // 画像を取得
  async getImage(id) {
    try {
      return await this.images.get(id);
    } catch (error) {
      console.error('画像取得エラー:', error);
      throw error;
    }
  }

  // すべての画像を取得
  async getAllImages() {
    try {
      return await this.images.orderBy('uploadDate').reverse().toArray();
    } catch (error) {
      console.error('画像一覧取得エラー:', error);
      throw error;
    }
  }

  // カテゴリで画像をフィルタリング
  async getImagesByCategory(category) {
    try {
      return await this.images.where('category').equals(category).toArray();
    } catch (error) {
      console.error('カテゴリ別画像取得エラー:', error);
      throw error;
    }
  }

  // タグで画像を検索
  async getImagesByTag(tag) {
    try {
      return await this.images.where('tags').anyOf([tag]).toArray();
    } catch (error) {
      console.error('タグ別画像取得エラー:', error);
      throw error;
    }
  }

  // 投資記録IDで画像を取得
  async getImagesByRecordId(recordId) {
    try {
      return await this.images.where('recordId').equals(recordId).toArray();
    } catch (error) {
      console.error('記録別画像取得エラー:', error);
      throw error;
    }
  }

  // 画像を検索
  async searchImages(query) {
    try {
      const lowerQuery = query.toLowerCase();
      return await this.images.filter(image => 
        image.originalName.toLowerCase().includes(lowerQuery) ||
        image.tags.some(tag => tag.toLowerCase().includes(lowerQuery)) ||
        image.category.toLowerCase().includes(lowerQuery)
      ).toArray();
    } catch (error) {
      console.error('画像検索エラー:', error);
      throw error;
    }
  }

  // 画像を更新
  async updateImage(id, updates) {
    try {
      return await this.images.update(id, updates);
    } catch (error) {
      console.error('画像更新エラー:', error);
      throw error;
    }
  }

  // 画像を削除
  async deleteImage(id) {
    try {
      return await this.images.delete(id);
    } catch (error) {
      console.error('画像削除エラー:', error);
      throw error;
    }
  }

  // 複数画像を一括削除
  async deleteMultipleImages(ids) {
    try {
      return await this.images.bulkDelete(ids);
    } catch (error) {
      console.error('複数画像削除エラー:', error);
      throw error;
    }
  }

  // カテゴリを保存
  async saveCategory(categoryData) {
    try {
      return await this.categories.add(categoryData);
    } catch (error) {
      console.error('カテゴリ保存エラー:', error);
      throw error;
    }
  }

  // すべてのカテゴリを取得
  async getAllCategories() {
    try {
      return await this.categories.toArray();
    } catch (error) {
      console.error('カテゴリ一覧取得エラー:', error);
      throw error;
    }
  }

  // タグを保存
  async saveTag(tagData) {
    try {
      return await this.tags.add(tagData);
    } catch (error) {
      console.error('タグ保存エラー:', error);
      throw error;
    }
  }

  // すべてのタグを取得
  async getAllTags() {
    try {
      return await this.tags.toArray();
    } catch (error) {
      console.error('タグ一覧取得エラー:', error);
      throw error;
    }
  }

  // データベース統計を取得
  async getDatabaseStats() {
    try {
      const totalImages = await this.images.count();
      const totalSize = await this.images.toArray().then(images => 
        images.reduce((sum, img) => sum + (img.fileSize || 0), 0)
      );
      const categories = await this.categories.count();
      const tags = await this.tags.count();

      return {
        totalImages,
        totalSize,
        totalCategories: categories,
        totalTags: tags,
        averageSize: totalImages > 0 ? Math.round(totalSize / totalImages) : 0
      };
    } catch (error) {
      console.error('統計取得エラー:', error);
      throw error;
    }
  }

  // データベースをクリア
  async clearDatabase() {
    try {
      await this.images.clear();
      await this.categories.clear();
      await this.tags.clear();
    } catch (error) {
      console.error('データベースクリアエラー:', error);
      throw error;
    }
  }
}

// シングルトンインスタンスを作成
const imageDB = new ImageDatabase();

// デフォルトカテゴリを初期化
const initializeDefaultCategories = async () => {
  try {
    const existingCategories = await imageDB.getAllCategories();
    if (existingCategories.length === 0) {
      const defaultCategories = [
        { name: 'チャート', description: '株価チャートや技術分析図', color: '#3B82F6' },
        { name: 'ニュース', description: 'ニュース記事やプレスリリース', color: '#10B981' },
        { name: '分析レポート', description: '投資分析レポートや調査資料', color: '#F59E0B' },
        { name: 'スクリーンショット', description: '取引画面やアプリのスクリーンショット', color: '#8B5CF6' },
        { name: 'その他', description: 'その他の投資関連画像', color: '#6B7280' }
      ];

      await imageDB.categories.bulkAdd(defaultCategories);
    }
  } catch (error) {
    console.error('デフォルトカテゴリ初期化エラー:', error);
  }
};

// 初期化を実行
initializeDefaultCategories();

export default imageDB;
