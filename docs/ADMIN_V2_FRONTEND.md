# Admin Dashboard V2 - Frontend Implementation

**Last Updated**: 2025-11-30 07:20 PST  
**Status**: Building UI Components

## Overview

Building the Admin Dashboard V2 frontend using:
- **Framework**: Next.js 14 (App Router)
- **UI Library**: Shadcn UI
- **Styling**: Tailwind CSS with glassmorphism
- **Icons**: Lucide React
- **State Management**: React hooks + SWR for data fetching

## Page Structure

### Main Admin Page (`/admin`)
**File**: `frontend/src/app/admin/page.tsx`

**Features**:
- Tabbed interface (Overview, Scraping, Analysis, Models, Prompts)
- Quick stats cards
- Recent activity feed
- Glassmorphism design matching main dashboard

**Tabs**:
1. **Overview** - Dashboard with stats and recent activity
2. **Scraping** - Manual scrape trigger and history
3. **Analysis** - Pipeline control (research → generate → review)
4. **Models** - Model configuration and priority management
5. **Prompts** - Prompt editor with version history

## Components to Build

### 1. Scrape Manager (`components/admin/ScrapeManager.tsx`)
**Purpose**: Trigger and monitor scraping operations

**Features**:
- Jurisdiction selector dropdown
- Force re-scrape checkbox
- Trigger button
- Real-time task status
- Scrape history table

**API Integration**:
```typescript
// Trigger scrape
POST /admin/scrape
{
  jurisdiction: string,
  force: boolean
}

// Get history
GET /admin/scrapes?jurisdiction={}&limit={}
```

### 2. Analysis Lab (`components/admin/AnalysisLab.tsx`)
**Purpose**: Run analysis pipeline steps

**Features**:
- Bill selector (jurisdiction + bill_id)
- Step selector (research, generate, review)
- Model override dropdown (optional)
- Run button
- Results viewer
- Analysis history table

**API Integration**:
```typescript
// Run analysis
POST /admin/analyze
{
  jurisdiction: string,
  bill_id: string,
  step: "research" | "generate" | "review",
  model_override?: string
}

// Get history
GET /admin/analyses?jurisdiction={}&bill_id={}&step={}
```

### 3. Model Registry (`components/admin/ModelRegistry.tsx`)
**Purpose**: Manage model configurations

**Features**:
- Model list with drag-and-drop priority reordering
- Enable/disable toggles
- Add new model form
- Health status indicators
- Usage statistics

**API Integration**:
```typescript
// Get models
GET /admin/models

// Update models
POST /admin/models
{
  models: Array<{
    provider: string,
    model_name: string,
    priority: number,
    enabled: boolean,
    use_case: string
  }>
}
```

### 4. Prompt Editor (`components/admin/PromptEditor.tsx`)
**Purpose**: Edit and version system prompts

**Features**:
- Prompt type selector (generation, review)
- Rich text editor for prompt content
- Version history viewer
- Activate/deactivate versions
- Diff viewer for version comparison

**API Integration**:
```typescript
// Get active prompt
GET /admin/prompts/{type}

// Update prompt (creates new version)
POST /admin/prompts
{
  prompt_type: "generation" | "review",
  system_prompt: string
}
```

### 5. Health Monitor (`components/admin/HealthMonitor.tsx`)
**Purpose**: Display system health status

**Features**:
- Service status cards (research, analysis, database, scrapers)
- Latency metrics
- Error rate graphs
- Auto-refresh every 30s

**API Integration**:
```typescript
// Get health
GET /admin/health/detailed
```

## Data Fetching Strategy

### Using SWR for Real-time Updates

```typescript
import useSWR from 'swr';

const fetcher = (url: string) => fetch(url).then(r => r.json());

function useModels() {
  const { data, error, mutate } = useSWR('/admin/models', fetcher, {
    refreshInterval: 30000 // Refresh every 30s
  });
  
  return {
    models: data,
    isLoading: !error && !data,
    isError: error,
    mutate
  };
}
```

## Styling Guidelines

### Glassmorphism Pattern
```css
/* Card background */
bg-white/10 backdrop-blur-md border-white/20

/* Hover state */
hover:bg-white/15

/* Active state */
data-[state=active]:bg-white/20
```

### Color Palette
- **Background**: `bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900`
- **Text**: `text-white` (primary), `text-slate-300` (secondary)
- **Borders**: `border-white/20`
- **Success**: `bg-green-500/20 text-green-300 border-green-500/30`
- **Error**: `bg-red-500/20 text-red-300 border-red-500/30`
- **Warning**: `bg-yellow-500/20 text-yellow-300 border-yellow-500/30`

## Implementation Progress

### ✅ Completed
- [x] Main admin page structure
- [x] Tabbed interface
- [x] Overview tab with stats cards
- [x] Placeholder tabs for all sections

### 🔄 In Progress
- [ ] Scrape Manager component
- [ ] Analysis Lab component
- [ ] Model Registry component
- [ ] Prompt Editor component
- [ ] Health Monitor component

### ⏳ Pending
- [ ] API integration with backend
- [ ] Real-time updates with SWR
- [ ] Form validation
- [ ] Error handling
- [ ] Loading states
- [ ] Toast notifications

## File Structure

```
frontend/src/
├── app/
│   └── admin/
│       └── page.tsx          # Main admin dashboard
├── components/
│   ├── admin/
│   │   ├── ScrapeManager.tsx
│   │   ├── AnalysisLab.tsx
│   │   ├── ModelRegistry.tsx
│   │   ├── PromptEditor.tsx
│   │   └── HealthMonitor.tsx
│   └── ui/                   # Shadcn components
└── lib/
    └── api/
        └── admin.ts          # API client functions
```

## Next Steps

1. ✅ Create main admin page structure
2. 🔄 Build Scrape Manager component
3. ⏳ Build Analysis Lab component
4. ⏳ Build Model Registry component
5. ⏳ Build Prompt Editor component
6. ⏳ Create API client functions
7. ⏳ Integrate with backend
8. ⏳ Add real-time updates
9. ⏳ Test end-to-end

## Blockers

None currently. Proceeding with component implementation.
