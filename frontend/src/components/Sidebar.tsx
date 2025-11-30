'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  FileSearch,
  Users,
  Briefcase,
  BarChart3,
  Settings,
  BrainCircuit,
  Info
} from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, href: '/' },
    { id: 'analyzer', label: 'Resume Analyzer', icon: FileSearch, href: '/analyzer' },
    { id: 'candidates', label: 'Candidates', icon: Users, href: '/candidates' },
    { id: 'jobs', label: 'Job Postings', icon: Briefcase, href: '/jobs' },
    { id: 'analytics', label: 'Analytics', icon: BarChart3, href: '/analytics' },
    { id: 'settings', label: 'Settings', icon: Settings, href: '/settings' },
    { id: 'admin', label: 'Admin', icon: Settings, href: '/admin' },
  ];

  // Glassmorphism styles using inline styles
  const glassStyle = {
    backdropFilter: 'blur(20px)',
    background: 'rgba(255, 255, 255, 0.15)',
    border: '1px solid rgba(255, 255, 255, 0.3)',
    boxShadow: '0 12px 40px rgba(31, 38, 135, 0.2)'
  };

  return (
    <aside className="w-64 shadow-2xl h-screen sticky top-0 flex flex-col" style={glassStyle}>
      {/* Header */}
      <div className="p-6 border-b border-white/20">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-teal-500 rounded-xl flex items-center justify-center">
            <BrainCircuit className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg text-gray-800 font-bold">AffordaBot</h1>
            <p className="text-xs text-gray-600">AI Legislation Analysis</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="p-4 space-y-2 flex-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.id}
              href={item.href}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-300 ${isActive
                ? 'bg-gradient-to-r from-purple-500 to-teal-500 text-white transform translate-x-1 shadow-lg'
                : 'text-gray-700 hover:bg-white/20 hover:translate-x-1'
                }`}
            >
              <Icon className="w-5 h-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Backend Status */}
      <div className="p-4 mt-auto">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-blue-100 text-blue-700 border border-blue-200">
          <Info className="w-4 h-4" />
          <span>v1.0.0 Beta</span>
        </div>
      </div>
    </aside>
  );
}