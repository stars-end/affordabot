import { test, expect } from '@playwright/test';

test.describe('Audit Trail Tests', () => {
    const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

    test('E2E-AUDIT-063017: Test audit trail retrieval via API', async ({ request }) => {
        // 1. First, check if backend is available
        try {
            await request.get(`${BACKEND_URL}/health`);
        } catch (error) {
            test.skip('Backend not available. Set BACKEND_URL env var or start backend server.');
        }

        // 2. Get a list of available runs/analyses
        const analysesResponse = await request.get(`${BACKEND_URL}/admin/analyses`);
        if (!analysesResponse.ok()) {
            test.skip('No analyses endpoint available or no analyses found.');
        }

        const analyses = await analysesResponse.json();
        if (!analyses || analyses.length === 0) {
            test.skip('No analysis history found. Run an analysis first via the Analysis Lab.');
        }

        // 3. Use the most recent analysis
        const runId = analyses[0].id || analyses[0].bill_id;

        // 4. Retrieve audit trail for a run
        const stepsResponse = await request.get(`${BACKEND_URL}/admin/runs/${runId}/steps`);

        // 5. Verify response is successful
        expect(stepsResponse.ok()).toBeTruthy();
        expect(stepsResponse.status()).toBe(200);

        // 6. Parse and validate audit trail data
        const steps = await stepsResponse.json();
        expect(Array.isArray(steps)).toBeTruthy();

        // 7. Verify audit trail contains expected step types
        if (steps.length > 0) {
            const stepNames = steps.map((s: any) => s.step_name);
            
            // Expected step types in the audit trail
            const expectedStepTypes = ['research', 'generate', 'review'];
            
            // Verify at least one expected step type is present
            const hasExpectedStep = expectedStepTypes.some(step => 
                stepNames.some(name => name.toLowerCase().includes(step))
            );
            expect(hasExpectedStep).toBeTruthy();

            // 8. Verify each audit step has required fields
            steps.forEach((step: any) => {
                expect(step).toHaveProperty('id');
                expect(step).toHaveProperty('run_id');
                expect(step).toHaveProperty('step_number');
                expect(step).toHaveProperty('step_name');
                expect(step).toHaveProperty('status');
                expect(step).toHaveProperty('created_at');

                // Status should be one of expected values
                const validStatuses = ['started', 'completed', 'failed', 'skipped'];
                expect(validStatuses).toContain(step.status);
            });

            // 9. Verify steps are ordered by step_number
            const stepNumbers = steps.map((s: any) => s.step_number);
            const sortedNumbers = [...stepNumbers].sort((a, b) => a - b);
            expect(stepNumbers).toEqual(sortedNumbers);
        }
    });

    test('E2E-AUDIT-063018: Verify audit trail contains model information', async ({ request }) => {
        try {
            await request.get(`${BACKEND_URL}/health`);
        } catch (error) {
            test.skip('Backend not available.');
        }

        // Get an analysis
        const analysesResponse = await request.get(`${BACKEND_URL}/admin/analyses`);
        if (!analysesResponse.ok()) test.skip('No analyses available.');
        const analyses = await analysesResponse.json();
        if (!analyses || analyses.length === 0) test.skip('No analysis history found.');
        
        const runId = analyses[0].id || analyses[0].bill_id;
        const response = await request.get(`${BACKEND_URL}/admin/runs/${runId}/steps`);
        expect(response.ok()).toBeTruthy();

        const steps = await response.json();
        if (steps.length > 0) {
            // Verify at least one step has model_info
            const stepsWithModel = steps.filter((s: any) => s.model_info && Object.keys(s.model_info).length > 0);
            expect(stepsWithModel.length).toBeGreaterThan(0);

            // Verify model_info structure
            stepsWithModel.forEach((step: any) => {
                expect(step.model_info).toHaveProperty('model');
            });
        }
    });

    test('E2E-AUDIT-063019: Verify audit trail includes duration metrics', async ({ request }) => {
        try {
            await request.get(`${BACKEND_URL}/health`);
        } catch (error) {
            test.skip('Backend not available.');
        }

        const analysesResponse = await request.get(`${BACKEND_URL}/admin/analyses`);
        if (!analysesResponse.ok()) test.skip('No analyses available.');
        const analyses = await analysesResponse.json();
        if (!analyses || analyses.length === 0) test.skip('No analysis history found.');
        
        const runId = analyses[0].id || analyses[0].bill_id;
        const response = await request.get(`${BACKEND_URL}/admin/runs/${runId}/steps`);
        expect(response.ok()).toBeTruthy();

        const steps = await response.json();
        if (steps.length > 0) {
            // Check that steps with completed status have duration_ms
            const completedSteps = steps.filter((s: any) => s.status === 'completed');
            if (completedSteps.length > 0) {
                completedSteps.forEach((step: any) => {
                    expect(step.duration_ms).toBeDefined();
                    expect(step.duration_ms).toBeGreaterThanOrEqual(0);
                });
            }
        }
    });
});
