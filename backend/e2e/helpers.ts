import { expect, Page } from '@playwright/test';

export const openHome = async (page: Page) => {
    await page.goto('/');
    await expect(
        page.getByPlaceholder('Search destinations or properties...')
    ).toBeVisible({ timeout: 10000 });
};

const skipOnboardingIfPresent = async (page: Page) => {
    const skipButton = page.getByRole('button', { name: 'Skip for now' });
    try {
        await skipButton.waitFor({ state: 'visible', timeout: 1500 });
        await skipButton.click();
    } catch {
        // No onboarding flow in the current session.
    }
};

export const loginAsDemoUser = async (page: Page, name = 'Alex Johnson') => {
    await page.getByRole('button', { name: 'Demo' }).click();
    await expect(page.getByText('Select a Demo User')).toBeVisible();
    await page.locator('button', { hasText: name }).first().click();
    await expect(page.getByRole('button', { name })).toBeVisible();
    await skipOnboardingIfPresent(page);
};

export const openUserMenu = async (page: Page, name = 'Alex Johnson') => {
    await page.getByRole('button', { name }).click();
};

export const openCoLivingHubFromMap = async (page: Page) => {
    const coLivingButton = page.getByRole('button', { name: 'Co-Living' });
    if (!(await coLivingButton.isVisible())) {
        await page.getByRole('button', { name: 'Stay', exact: true }).click();
    }
    const coLivingClass = await coLivingButton.getAttribute('class');
    if (!coLivingClass?.includes('bg-indigo-600')) {
        await coLivingButton.click();
    }

    const mapContainer = page.getByAltText('World Map').locator('..').locator('..');
    const mapPin = mapContainer.locator('button').first();
    await expect(mapPin).toBeVisible({ timeout: 10000 });
    await mapPin.click();
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
};
