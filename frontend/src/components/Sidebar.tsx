'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const JURISDICTIONS = [
    { id: 'california', name: 'California State' },
    { id: 'santa-clara-county', name: 'Santa Clara County' },
    { id: 'san-jose', name: 'San Jose City' },
    { id: 'saratoga', name: 'Saratoga City' },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="w-64 bg-white border-r border-gray-200 min-h-screen flex-shrink-0 hidden md:block">
            <div className="p-6">
                <Link href="/" className="flex items-center gap-2 mb-8">
                    <span className="text-2xl">🤖</span>
                    <span className="font-bold text-xl text-gray-900">AffordaBot</span>
                </Link>

                <nav className="space-y-1">
                    <Link
                        href="/"
                        className={`block px-3 py-2 rounded-md text-sm font-medium ${pathname === '/'
                                ? 'bg-blue-50 text-blue-700'
                                : 'text-gray-700 hover:bg-gray-50'
                            }`}
                    >
                        Home
                    </Link>

                    <div className="pt-4 pb-2">
                        <p className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                            Jurisdictions
                        </p>
                    </div>

                    {JURISDICTIONS.map((jur) => (
                        <Link
                            key={jur.id}
                            href={`/dashboard/${jur.id}`}
                            className={`block px-3 py-2 rounded-md text-sm font-medium ${pathname === `/dashboard/${jur.id}`
                                    ? 'bg-blue-50 text-blue-700'
                                    : 'text-gray-700 hover:bg-gray-50'
                                }`}
                        >
                            {jur.name}
                        </Link>
                    ))}

                    <div className="pt-4 pb-2">
                        <p className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                            Resources
                        </p>
                    </div>

                    <Link
                        href="/admin"
                        className={`block px-3 py-2 rounded-md text-sm font-medium ${pathname === '/admin'
                                ? 'bg-blue-50 text-blue-700'
                                : 'text-gray-700 hover:bg-gray-50'
                            }`}
                    >
                        Admin Dashboard
                    </Link>
                </nav>
            </div>
        </div>
    );
}
