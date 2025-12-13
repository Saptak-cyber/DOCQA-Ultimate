'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/Button';
import { FileText, Zap, Shield } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white">
      <div className="container-custom py-16">
        {/* Header */}
        <header className="flex justify-between items-center mb-16">
          <h1 className="text-2xl font-bold text-primary-600">DOCQA Ultimate</h1>
          <div className="flex space-x-4">
            <Link href="/login">
              <Button variant="ghost">Login</Button>
            </Link>
            <Link href="/signup">
              <Button>Sign Up</Button>
            </Link>
          </div>
        </header>

        {/* Hero Section */}
        <div className="text-center mb-20">
          <h2 className="text-5xl font-bold text-gray-900 mb-6">
            Ask Questions About Your Documents
          </h2>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Upload PDFs, get instant answers with AI-powered document understanding.
            Powered by RAG technology for accurate, citation-backed responses.
          </p>
          <div className="flex justify-center space-x-4">
            <Link href="/signup">
              <Button size="lg">Get Started</Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="secondary">
                Sign In
              </Button>
            </Link>
          </div>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-8 mt-20">
          <div className="text-center p-6">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-100 rounded-lg mb-4">
              <FileText className="h-6 w-6 text-primary-600" />
            </div>
            <h3 className="text-xl font-semibold mb-2">Document Upload</h3>
            <p className="text-gray-600">
              Upload PDF documents and let our system process and index them automatically.
            </p>
          </div>

          <div className="text-center p-6">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-100 rounded-lg mb-4">
              <Zap className="h-6 w-6 text-primary-600" />
            </div>
            <h3 className="text-xl font-semibold mb-2">AI-Powered Search</h3>
            <p className="text-gray-600">
              Ask questions in natural language and get accurate answers with source citations.
            </p>
          </div>

          <div className="text-center p-6">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-100 rounded-lg mb-4">
              <Shield className="h-6 w-6 text-primary-600" />
            </div>
            <h3 className="text-xl font-semibold mb-2">Secure & Private</h3>
            <p className="text-gray-600">
              Your documents are securely stored and only accessible by you.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
