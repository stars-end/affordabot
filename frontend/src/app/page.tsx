'use client';

import { Title, Text, Card, Button, Metric } from '@tremor/react';
import Link from 'next/link';
import Sidebar from '@/components/Sidebar';

export default function LandingPage() {
  // Mock data for top bills
  const topBills = [
    {
      id: 'SB-423',
      title: 'Streamlined Housing Approvals in Coastal Zones',
      impact: 1250,
      jurisdiction: 'California State',
      type: 'savings'
    },
    {
      id: 'AB-12',
      title: 'Tenant Security Deposit Cap Amendment',
      impact: 450,
      jurisdiction: 'California State',
      type: 'savings'
    },
    {
      id: 'ORD-24-01',
      title: 'Residential Electrification Mandate',
      impact: -3200,
      jurisdiction: 'San Jose',
      type: 'cost'
    },
    {
      id: 'MEASURE-A',
      title: 'Affordable Housing Bond 2024',
      impact: -180,
      jurisdiction: 'Santa Clara County',
      type: 'cost'
    },
    {
      id: 'SB-4',
      title: 'Affordable Housing on Faith Lands',
      impact: 850,
      jurisdiction: 'California State',
      type: 'savings'
    }
  ];

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />

      <main className="flex-1 p-8">
        {/* Hero Section */}
        <div className="max-w-5xl mx-auto mb-16 text-center">
          <div className="inline-block p-2 bg-blue-100 rounded-full mb-4">
            <span className="text-blue-800 font-semibold text-sm px-2">
              🤖 Automated Affordability Analysis
            </span>
          </div>

          <h1 className="text-5xl font-bold text-gray-900 mb-6 leading-tight">
            Track how new legislation affects<br />
            <span className="text-blue-600">your cost of living</span>
          </h1>

          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Get automated alerts when new legislation impacts housing, healthcare,
            and daily expenses, with AI-powered analysis and evidence-based estimates.
          </p>

          <div className="flex justify-center gap-4">
            <Link href="/dashboard/california">
              <Button size="xl" variant="primary">
                View California Dashboard
              </Button>
            </Link>
            <Link href="#how-it-works">
              <Button size="xl" variant="secondary">
                How It Works
              </Button>
            </Link>
          </div>
        </div>

        {/* Beautiful Graphic / Summary Section */}
        <div className="max-w-6xl mx-auto mb-16">
          <Card className="bg-gradient-to-br from-slate-900 to-slate-800 text-white border-none overflow-hidden relative">
            <div className="absolute top-0 right-0 w-1/2 h-full opacity-10 bg-[url('https://upload.wikimedia.org/wikipedia/commons/0/01/California_in_United_States.svg')] bg-no-repeat bg-contain bg-right-center pointer-events-none"></div>

            <div className="relative z-10 p-8">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div>
                  <Text className="text-slate-400 uppercase tracking-wider text-xs font-bold">Total Bills Analyzed</Text>
                  <Metric className="text-white mt-2">1,247</Metric>
                  <Text className="text-slate-400 text-sm mt-1">Across 4 jurisdictions</Text>
                </div>
                <div>
                  <Text className="text-slate-400 uppercase tracking-wider text-xs font-bold">Net Annual Impact</Text>
                  <Metric className="text-emerald-400 mt-2">-$450</Metric>
                  <Text className="text-slate-400 text-sm mt-1">Per household (avg)</Text>
                </div>
                <div>
                  <Text className="text-slate-400 uppercase tracking-wider text-xs font-bold">Active Alerts</Text>
                  <Metric className="text-white mt-2">12</Metric>
                  <Text className="text-slate-400 text-sm mt-1">High-priority items</Text>
                </div>
              </div>

              <div className="mt-12">
                <h3 className="text-xl font-bold mb-6">Top 5 High-Impact Bills</h3>
                <div className="space-y-4">
                  {topBills.map((bill, idx) => (
                    <div key={bill.id} className="flex items-center justify-between bg-white/5 p-4 rounded-lg hover:bg-white/10 transition-colors cursor-pointer group">
                      <div className="flex items-center gap-4">
                        <span className="text-slate-500 font-mono text-sm">0{idx + 1}</span>
                        <div>
                          <p className="font-semibold text-white group-hover:text-blue-300 transition-colors">{bill.title}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs bg-white/10 px-2 py-0.5 rounded text-slate-300">{bill.id}</span>
                            <span className="text-xs text-slate-400">{bill.jurisdiction}</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-bold ${bill.type === 'savings' ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {bill.type === 'savings' ? '+' : ''}${bill.impact}/yr
                        </p>
                        <p className="text-xs text-slate-500">Est. Impact</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Mission Section */}
        <div className="max-w-4xl mx-auto text-center mb-16" id="how-it-works">
          <h2 className="text-3xl font-bold text-gray-900 mb-8">Our Mission</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div className="text-4xl mb-4">🔍</div>
              <h3 className="font-bold text-lg mb-2">Monitor</h3>
              <p className="text-gray-600 text-sm">
                We track every bill and regulation across state and local jurisdictions in real-time.
              </p>
            </div>
            <div className="p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div className="text-4xl mb-4">🧠</div>
              <h3 className="font-bold text-lg mb-2">Analyze</h3>
              <p className="text-gray-600 text-sm">
                Our AI reads thousands of pages to extract hidden costs and savings for families.
              </p>
            </div>
            <div className="p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div className="text-4xl mb-4">📢</div>
              <h3 className="font-bold text-lg mb-2">Alert</h3>
              <p className="text-gray-600 text-sm">
                We notify you of high-impact changes so you can take action before it's law.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
