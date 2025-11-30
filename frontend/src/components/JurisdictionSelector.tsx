'use client';

import { Select, SelectItem } from '@tremor/react';
import { JURISDICTIONS, type Jurisdiction } from '@/lib/api';

interface JurisdictionSelectorProps {
    selected: Jurisdiction;
    onChange: (jurisdiction: Jurisdiction) => void;
}

export default function JurisdictionSelector({ selected, onChange }: JurisdictionSelectorProps) {
    return (
        <div className="w-full max-w-xs">
            <Select
                value={selected}
                onValueChange={(value) => onChange(value as Jurisdiction)}
                placeholder="Select jurisdiction..."
            >
                {JURISDICTIONS.map((jur) => (
                    <SelectItem key={jur.id} value={jur.id}>
                        <div className="flex items-center gap-2">
                            <span className="text-xs px-2 py-0.5 bg-gray-100 rounded-full capitalize">
                                {jur.type}
                            </span>
                            {jur.name}
                        </div>
                    </SelectItem>
                ))}
            </Select>
        </div>
    );
}
