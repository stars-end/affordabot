import Link from 'next/link';

export default function Navbar() {
    return (
        <nav className="bg-white border-b border-tremor-border shadow-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                    <div className="flex">
                        <div className="flex-shrink-0 flex items-center">
                            <Link href="/" className="text-2xl font-bold text-tremor-brand-emphasis">
                                AffordaBot
                            </Link>
                            <span className="ml-2 text-xs px-2 py-1 bg-tremor-brand-faint text-tremor-brand-emphasis rounded-full">
                                Beta
                            </span>
                        </div>
                        <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                            <Link
                                href="/"
                                className="border-tremor-brand-emphasis text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                            >
                                Dashboard
                            </Link>
                            <Link
                                href="/about"
                                className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                            >
                                About
                            </Link>
                        </div>
                    </div>
                    <div className="flex items-center">
                        <button className="bg-tremor-brand-emphasis text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">
                            Subscribe for Alerts
                        </button>
                    </div>
                </div>
            </div>
        </nav>
    );
}
