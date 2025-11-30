'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Building2, MapPin, Settings, FileText, Shield } from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();

  const menuItems = [
    { id: 'california', label: 'California', icon: MapPin, path: '/dashboard/california' },
    { id: 'santa-clara', label: 'Santa Clara Co.', icon: MapPin, path: '/dashboard/santa-clara-county' },
    { id: 'san-jose', label: 'San Jose', icon: Building2, path: '/dashboard/san-jose' },
    { id: 'saratoga', label: 'Saratoga', icon: Building2, path: '/dashboard/saratoga' },
    { id: 'admin', label: 'Admin Console', icon: Shield, path: '/admin' },
  ];

  return (
    <div className="w-64 bg-white/10 backdrop-blur-md border-r border-white/20 min-h-screen p-6 flex flex-col">
      <div className="flex items-center gap-3 mb-10 px-2">
        <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-blue-600 rounded-xl flex items-center justify-center shadow-lg">
          <FileText className="text-white w-6 h-6" />
        </div>
        <div>
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-blue-600">
            AffordaBot
          </h1>
          <p className="text-xs text-gray-500">Legislation Analysis</p>
        </div>
      </div>

      <nav className="space-y-2 flex-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.path;

          return (
            <Link
              key={item.id}
              href={item.path}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${isActive
                ? 'bg-white/20 text-purple-700 shadow-sm border border-white/20'
                : 'text-gray-600 hover:bg-white/10 hover:text-purple-600'
                }`}
            >
              <Icon className={`w-5 h-5 transition-colors ${isActive ? 'text-purple-600' : 'text-gray-400 group-hover:text-purple-500'
                }`} />
              <span className="font-medium">{item.label}</span>
              {isActive && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)]"></div>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto pt-6 border-t border-white/10">
        <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 rounded-xl p-4 border border-white/20">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
              <span className="text-xs font-bold text-purple-600">AI</span>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-800">Analysis Active</p>
              <p className="text-xs text-gray-500">Monitoring bills...</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}