'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useUser } from '@clerk/nextjs';
import { LayoutDashboard, Building2, MapPin, Settings, FileText, Shield } from 'lucide-react';

export function Sidebar() {
  const pathname = usePathname();
  const { isSignedIn } = useUser();

  // Public menu items - visible to all users
  const publicMenuItems = [
    { id: 'california', label: 'California', icon: MapPin, path: '/dashboard/california' },
    { id: 'santa-clara', label: 'Santa Clara Co.', icon: MapPin, path: '/dashboard/santa-clara-county' },
    { id: 'san-jose', label: 'San Jose', icon: Building2, path: '/dashboard/san-jose' },
    { id: 'saratoga', label: 'Saratoga', icon: Building2, path: '/dashboard/saratoga' },
  ];

  // Admin menu items - only visible to authenticated users
  const adminMenuItems = [
    { id: 'admin', label: 'Admin Console', icon: Shield, path: '/admin' },
    { id: 'admin-discovery', label: '↳ Discovery', icon: LayoutDashboard, path: '/admin/discovery' },
    { id: 'admin-sources', label: '↳ Sources', icon: Settings, path: '/admin/sources' },
    { id: 'admin-prompts', label: '↳ Prompts', icon: FileText, path: '/admin/prompts' },
    { id: 'admin-reviews', label: '↳ Reviews', icon: Shield, path: '/admin/reviews' },
    { id: 'admin-audits', label: '↳ Audit Trace', icon: Settings, path: '/admin/audits/trace' },
  ];

  // Combine menu items: show admin items only if signed in
  const menuItems = isSignedIn
    ? [...publicMenuItems, ...adminMenuItems]
    : publicMenuItems;

  return (
    <div className="w-64 bg-white border-r border-slate-200 min-h-screen p-6 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 mb-10 px-2">
        <div className="w-10 h-10 relative">
          {/* Prism logo - overlapping triangles */}
          <svg viewBox="0 0 40 40" className="w-full h-full">
            <polygon points="20,4 32,32 8,32" fill="#22d3ee" opacity="0.8" />
            <polygon points="20,8 30,30 10,30" fill="#fbbf24" opacity="0.8" transform="translate(2, -1)" />
            <polygon points="20,12 28,28 12,28" fill="#f472b6" opacity="0.8" transform="translate(-1, 1)" />
          </svg>
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">AFFORDABOT</h1>
          <p className="text-xs text-slate-500 uppercase tracking-wider">Solid Sculpture Refraction</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="space-y-1 flex-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.path;

          return (
            <Link
              key={item.id}
              href={item.path}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded transition-all duration-150 text-sm font-medium ${isActive
                  ? 'bg-slate-900 text-white'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Status indicator */}
      <div className="mt-auto pt-6 border-t border-slate-200">
        <div className="flex items-center gap-3 px-2">
          <div className="w-2 h-2 rounded-full bg-prism-green animate-pulse" />
          <div>
            <p className="text-sm font-medium text-slate-700">System Online</p>
            <p className="text-xs text-slate-500">Monitoring active</p>
          </div>
        </div>
      </div>
    </div>
  );
}
