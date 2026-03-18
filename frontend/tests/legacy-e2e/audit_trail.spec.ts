import { test, expect } from '@playwright/test';

test.describe('Audit Trail Tests', () => {
  const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

  test('E2E-AUDIT-063017: Test audit trail retrieval via API', async ({ request }) => {
    try {
      await request.get(`${BACKEND_URL}/health`);
    } catch (error) {
      test.skip('Backend not available. Set BACKEND_URL env var or start backend server.');
    }

    const analysesResponse = await request.get(`${BACKEND_URL}/admin/analyses`);
    if (!analysesResponse.ok()) {
      test.skip('No analyses endpoint available or no analyses found.');
    }

    const analyses = await analysesResponse.json();
    if (!analyses || analyses.length === 0) {
      test.skip('No analysis history found. Run an analysis first via the Analysis Lab.');
    }

    const runId = analyses[0].id || analyses[0].bill_id;
    const stepsResponse = await request.get(`${BACKEND_URL}/admin/runs/${runId}/steps`);

    expect(stepsResponse.ok()).toBeTruthy();
    expect(stepsResponse.status()).toBe(200);

    const steps = await stepsResponse.json();
    expect(Array.isArray(steps)).toBeTruthy();

    if (steps.length > 0) {
      const stepNames = steps.map((step: any) => step.step_name);
      const expectedStepTypes = ['research', 'generate', 'review'];
      const hasExpectedStep = expectedStepTypes.some((step) =>
        stepNames.some((name) => name.toLowerCase().includes(step))
      );
      expect(hasExpectedStep).toBeTruthy();

      steps.forEach((step: any) => {
        expect(step).toHaveProperty('id');
        expect(step).toHaveProperty('run_id');
        expect(step).toHaveProperty('step_number');
        expect(step).toHaveProperty('step_name');
        expect(step).toHaveProperty('status');
        expect(step).toHaveProperty('created_at');
        expect(['started', 'completed', 'failed', 'skipped']).toContain(step.status);
      });

      const stepNumbers = steps.map((step: any) => step.step_number);
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

    const analysesResponse = await request.get(`${BACKEND_URL}/admin/analyses`);
    if (!analysesResponse.ok()) {
      test.skip('No analyses available.');
    }

    const analyses = await analysesResponse.json();
    if (!analyses || analyses.length === 0) {
      test.skip('No analysis history found.');
    }

    const runId = analyses[0].id || analyses[0].bill_id;
    const response = await request.get(`${BACKEND_URL}/admin/runs/${runId}/steps`);
    expect(response.ok()).toBeTruthy();

    const steps = await response.json();
    if (steps.length > 0) {
      const stepsWithModel = steps.filter((step: any) => step.model_info && Object.keys(step.model_info).length > 0);
      expect(stepsWithModel.length).toBeGreaterThan(0);

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
    if (!analysesResponse.ok()) {
      test.skip('No analyses available.');
    }

    const analyses = await analysesResponse.json();
    if (!analyses || analyses.length === 0) {
      test.skip('No analysis history found.');
    }

    const runId = analyses[0].id || analyses[0].bill_id;
    const response = await request.get(`${BACKEND_URL}/admin/runs/${runId}/steps`);
    expect(response.ok()).toBeTruthy();

    const steps = await response.json();
    if (steps.length > 0) {
      const completedSteps = steps.filter((step: any) => step.status === 'completed');
      if (completedSteps.length > 0) {
        completedSteps.forEach((step: any) => {
          expect(step.duration_ms).toBeDefined();
          expect(step.duration_ms).toBeGreaterThanOrEqual(0);
        });
      }
    }
  });
});
