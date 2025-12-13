'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { documentsApi } from '@/lib/api/documents';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { Upload, FileText, X } from 'lucide-react';
import { ACCEPTED_FILE_TYPES } from '@/lib/utils/constants';
import { formatFileSize } from '@/lib/utils/formatFileSize';

interface UploadedFile {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  documentId?: string;
  error?: string;
}

export function DocumentUpload() {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError(null);
    
    acceptedFiles.forEach((file) => {
      // Add to upload queue
      const uploadFile: UploadedFile = {
        file,
        status: 'pending',
      };
      
      setUploadedFiles((prev) => [...prev, uploadFile]);

      // Start upload
      uploadFile.status = 'uploading';
      setUploadedFiles((prev) => [...prev]);

      documentsApi
        .uploadDocument(file)
        .then((response) => {
          setUploadedFiles((prev) =>
            prev.map((f) =>
              f.file === file
                ? { ...f, status: 'success', documentId: response.document_id }
                : f
            )
          );
        })
        .catch((err: any) => {
          setUploadedFiles((prev) =>
            prev.map((f) =>
              f.file === file
                ? {
                    ...f,
                    status: 'error',
                    error: err.response?.data?.detail || 'Upload failed',
                  }
                : f
            )
          );
        });
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  });

  const removeFile = (file: File) => {
    setUploadedFiles((prev) => prev.filter((f) => f.file !== file));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Documents</h2>
        <p className="text-gray-600">
          Upload PDF files to process and index them for querying
        </p>
      </div>

      {error && (
        <Alert type="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card>
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
          }`}
        >
          <input {...getInputProps()} />
          <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          {isDragActive ? (
            <p className="text-primary-600 font-medium">Drop the files here...</p>
          ) : (
            <>
              <p className="text-gray-700 font-medium mb-2">
                Drag & drop PDF files here, or click to select
              </p>
            </>
          )}
        </div>
      </Card>

      {uploadedFiles.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-gray-900">Upload Queue</h3>
          {uploadedFiles.map((uploadFile, index) => (
            <Card key={index} className="flex items-center justify-between">
              <div className="flex items-center space-x-3 flex-1 min-w-0">
                <FileText className="h-5 w-5 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {uploadFile.file.name}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatFileSize(uploadFile.file.size)}
                  </p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                {uploadFile.status === 'uploading' && (
                  <div className="flex items-center space-x-2 text-sm text-blue-600">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                    <span>Uploading...</span>
                  </div>
                )}
                {uploadFile.status === 'success' && (
                  <span className="text-sm text-green-600 font-medium">
                    ✓ Queued
                  </span>
                )}
                {uploadFile.status === 'error' && (
                  <span className="text-sm text-red-600">
                    {uploadFile.error}
                  </span>
                )}
                <button
                  onClick={() => removeFile(uploadFile.file)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
