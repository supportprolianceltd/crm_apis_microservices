import { createClient } from '@supabase/supabase-js';
import { S3Client, PutObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import fs from 'fs';
import path from 'path';

// Storage platform configurations
const STORAGE_PLATFORMS = {
  LOCAL: 'local',
  SUPABASE: 'supabase',
  S3: 's3'
};

// Get storage configuration from environment
const getStorageConfig = () => {
  const platform = process.env.STORAGE_PLATFORM || STORAGE_PLATFORMS.SUPABASE;
  const config = {
    platform,
    local: {
      uploadDir: process.env.LOCAL_UPLOAD_DIR || 'uploads'
    },
    supabase: {
      url: process.env.SUPABASE_URL,
      key: process.env.SUPABASE_KEY,
      bucket: process.env.SUPABASE_BUCKET || 'luminacaremedia'
    },
    s3: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      region: process.env.AWS_REGION || 'us-east-1',
      bucket: process.env.AWS_S3_BUCKET,
      cloudfrontUrl: process.env.AWS_CLOUDFRONT_URL // Optional CloudFront distribution
    }
  };

  return config;
};

// Initialize Supabase client
let supabaseClient = null;
const getSupabaseClient = () => {
  if (!supabaseClient) {
    const config = getStorageConfig();
    supabaseClient = createClient(config.supabase.url, config.supabase.key);
  }
  return supabaseClient;
};

// Initialize S3 client
let s3Client = null;
const getS3Client = () => {
  if (!s3Client) {
    const config = getStorageConfig();
    s3Client = new S3Client({
      region: config.s3.region,
      credentials: {
        accessKeyId: config.s3.accessKeyId,
        secretAccessKey: config.s3.secretAccessKey,
      },
    });
  }
  return s3Client;
};

export const FileStorageService = {
  // Upload file to configured storage platform
  async uploadFile(file, folder = 'messages') {
    const config = getStorageConfig();

    try {
      if (config.platform === STORAGE_PLATFORMS.SUPABASE) {
        return await this.uploadToSupabase(file, folder);
      } else if (config.platform === STORAGE_PLATFORMS.S3) {
        return await this.uploadToS3(file, folder);
      } else if (config.platform === STORAGE_PLATFORMS.LOCAL) {
        return await this.uploadToLocal(file, folder);
      } else {
        throw new Error(`Unsupported storage platform: ${config.platform}`);
      }
    } catch (error) {
      console.error('Error uploading file:', error);
      throw new Error('Failed to upload file');
    }
  },

  // Upload to Supabase Storage
  async uploadToSupabase(file, folder) {
    const supabase = getSupabaseClient();
    const config = getStorageConfig();

    // Generate unique filename
    const fileExt = path.extname(file.originalname);
    const fileName = `${folder}/${Date.now()}-${Math.random().toString(36).substring(2)}${fileExt}`;

    try {
      // Read file buffer
      const fileBuffer = fs.readFileSync(file.path);

      // Upload to Supabase
      const { data, error } = await supabase.storage
        .from(config.supabase.bucket)
        .upload(fileName, fileBuffer, {
          contentType: file.mimetype,
          upsert: false
        });

      if (error) {
        throw error;
      }

      // Get public URL
      const { data: urlData } = supabase.storage
        .from(config.supabase.bucket)
        .getPublicUrl(fileName);

      // Clean up local temp file
      fs.unlinkSync(file.path);

      return {
        url: urlData.publicUrl,
        fileName: file.originalname,
        fileSize: file.size,
        fileType: file.mimetype,
        storagePath: fileName,
        platform: STORAGE_PLATFORMS.SUPABASE
      };
    } catch (error) {
      // Clean up local temp file on error
      if (fs.existsSync(file.path)) {
        fs.unlinkSync(file.path);
      }
      throw error;
    }
  },

  // Upload to local storage (fallback)
  async uploadToLocal(file, folder) {
    const config = getStorageConfig();

    // Ensure upload directory exists
    const uploadDir = path.join(config.local.uploadDir, folder);
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }

    // Generate unique filename
    const fileExt = path.extname(file.originalname);
    const fileName = `${Date.now()}-${Math.random().toString(36).substring(2)}${fileExt}`;
    const filePath = path.join(uploadDir, fileName);

    try {
      // Move file to final location
      fs.renameSync(file.path, filePath);

      return {
        url: `/uploads/${folder}/${fileName}`,
        fileName: file.originalname,
        fileSize: file.size,
        fileType: file.mimetype,
        storagePath: `${folder}/${fileName}`,
        platform: STORAGE_PLATFORMS.LOCAL
      };
    } catch (error) {
      // Clean up temp file on error
      if (fs.existsSync(file.path)) {
        fs.unlinkSync(file.path);
      }
      throw error;
    }
  },

  // Delete file from storage
  async deleteFile(storagePath, platform = null) {
    const config = getStorageConfig();
    const storagePlatform = platform || config.platform;

    try {
      if (storagePlatform === STORAGE_PLATFORMS.SUPABASE) {
        return await this.deleteFromSupabase(storagePath);
      } else if (storagePlatform === STORAGE_PLATFORMS.S3) {
        return await this.deleteFromS3(storagePath);
      } else if (storagePlatform === STORAGE_PLATFORMS.LOCAL) {
        return await this.deleteFromLocal(storagePath);
      } else {
        throw new Error(`Unsupported storage platform: ${storagePlatform}`);
      }
    } catch (error) {
      console.error('Error deleting file:', error);
      throw new Error('Failed to delete file');
    }
  },

  // Delete from Supabase
  async deleteFromSupabase(storagePath) {
    const supabase = getSupabaseClient();
    const config = getStorageConfig();

    const { error } = await supabase.storage
      .from(config.supabase.bucket)
      .remove([storagePath]);

    if (error) {
      throw error;
    }

    return true;
  },

  // Upload to Amazon S3
  async uploadToS3(file, folder) {
    const s3 = getS3Client();
    const config = getStorageConfig();

    // Generate unique filename
    const fileExt = path.extname(file.originalname);
    const fileName = `${folder}/${Date.now()}-${Math.random().toString(36).substring(2)}${fileExt}`;

    try {
      // Read file buffer
      const fileBuffer = fs.readFileSync(file.path);

      // Upload to S3
      const uploadCommand = new PutObjectCommand({
        Bucket: config.s3.bucket,
        Key: fileName,
        Body: fileBuffer,
        ContentType: file.mimetype,
        ACL: 'public-read', // Make file publicly accessible
      });

      await s3.send(uploadCommand);

      // Generate public URL
      const url = config.s3.cloudfrontUrl
        ? `${config.s3.cloudfrontUrl}/${fileName}`
        : `https://${config.s3.bucket}.s3.${config.s3.region}.amazonaws.com/${fileName}`;

      // Clean up local temp file
      fs.unlinkSync(file.path);

      return {
        url: url,
        fileName: file.originalname,
        fileSize: file.size,
        fileType: file.mimetype,
        storagePath: fileName,
        platform: STORAGE_PLATFORMS.S3
      };
    } catch (error) {
      // Clean up local temp file on error
      if (fs.existsSync(file.path)) {
        fs.unlinkSync(file.path);
      }
      throw error;
    }
  },

  // Delete from local storage
  async deleteFromLocal(storagePath) {
    const config = getStorageConfig();
    const filePath = path.join(config.local.uploadDir, storagePath);

    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
    }

    return true;
  },

  // Delete from S3
  async deleteFromS3(storagePath) {
    const s3 = getS3Client();
    const config = getStorageConfig();

    const deleteCommand = new DeleteObjectCommand({
      Bucket: config.s3.bucket,
      Key: storagePath,
    });

    await s3.send(deleteCommand);
    return true;
  },

  // Get file URL (for accessing stored files)
  getFileUrl(storagePath, platform = null) {
    const config = getStorageConfig();
    const storagePlatform = platform || config.platform;

    if (storagePlatform === STORAGE_PLATFORMS.SUPABASE) {
      const supabase = getSupabaseClient();
      const { data } = supabase.storage
        .from(config.supabase.bucket)
        .getPublicUrl(storagePath);
      return data.publicUrl;
    } else if (storagePlatform === STORAGE_PLATFORMS.S3) {
      return config.s3.cloudfrontUrl
        ? `${config.s3.cloudfrontUrl}/${storagePath}`
        : `https://${config.s3.bucket}.s3.${config.s3.region}.amazonaws.com/${storagePath}`;
    } else if (storagePlatform === STORAGE_PLATFORMS.LOCAL) {
      return `/uploads/${storagePath}`;
    } else {
      throw new Error(`Unsupported storage platform: ${storagePlatform}`);
    }
  }
};