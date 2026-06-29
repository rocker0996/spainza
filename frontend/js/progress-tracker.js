/**
 * Application Progress Tracker for Dashboard
 * Dynamically loads and displays application progress stages
 */

(function () {
  const API_BASE = window.location.protocol === 'file:'
    ? 'http://localhost:5000/api'
    : '/api';

  /**
   * Fetch application progress from API
   */
  async function fetchApplicationProgress() {
    try {
      const response = await fetch(`${API_BASE}/application/progress`, {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Error fetching application progress:', error);
      return null;
    }
  }

  /**
   * Render stage icon based on status
   */
  function renderStageIcon(stage) {
    if (stage.is_completed) {
      return `
        <div class="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center z-10 shrink-0">
          <span class="material-symbols-outlined text-primary-container text-[16px]">check</span>
        </div>
      `;
    } else if (stage.is_active) {
      return `
        <div class="w-8 h-8 rounded-full bg-surface-container-lowest border-2 border-tertiary-container flex items-center justify-center z-10 shrink-0">
          <div class="w-2.5 h-2.5 rounded-full bg-tertiary-container animate-pulse"></div>
        </div>
      `;
    } else {
      return `
        <div class="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center z-10 shrink-0">
          <span class="material-symbols-outlined text-outline text-[16px]">schedule</span>
        </div>
      `;
    }
  }

  /**
   * Render stage content
   */
  function renderStageContent(stage, locale = 'ru') {
    const title = locale === 'ru' ? stage.title_ru : stage.title_en;
    const description = locale === 'ru' ? stage.description_ru : stage.description_en;

    if (stage.is_active) {
      return `
        <div class="bg-surface-container-low p-5 rounded-[12px] flex-1">
          <div class="flex justify-between items-start mb-2">
            <h3 class="text-base font-semibold font-headline text-on-surface">${title}</h3>
            <span class="bg-tertiary-container text-on-tertiary px-2 py-1 rounded-[4px] text-[10px] font-bold uppercase tracking-wider font-label">
              ${locale === 'ru' ? 'Текущий этап' : 'Current Stage'}
            </span>
          </div>
          <p class="text-sm text-on-surface-variant font-body mb-4">${description}</p>
        </div>
      `;
    } else {
      return `
        <div>
          <h3 class="text-base font-semibold font-headline text-on-surface">${title}</h3>
          <p class="text-sm text-on-surface-variant font-body mt-1">${description}</p>
          ${stage.completed_date ? `<p class="text-xs text-outline mt-1">${locale === 'ru' ? 'Завершено' : 'Completed'}: ${formatStageDate(stage.completed_date)}</p>` : ''}
        </div>
      `;
    }
  }

  /**
   * Render complete timeline
   */
  function renderTimeline(stages, locale = 'ru') {
    const stagesHtml = stages.map((stage, index) => {
      const opacity = stage.is_completed || stage.is_active ? '' : 'opacity-50';

      return `
        <div class="flex gap-6 relative ${opacity}">
          ${renderStageIcon(stage)}
          ${renderStageContent(stage, locale)}
        </div>
      `;
    }).join('');

    return `
      <div class="flex flex-col gap-6 relative pl-6">
        <!-- Vertical line connecting steps -->
        <div class="absolute left-[31px] top-4 bottom-8 w-[2px] bg-outline-variant/20"></div>
        ${stagesHtml}
      </div>
    `;
  }

  function formatStageDate(value) {
    const date = window.LkI18n?.parseInstant(value) || new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    const localeTag = window.LkI18n ? window.LkI18n.dateLocaleTag() : "ru-RU";
    return date.toLocaleDateString(localeTag);
  }

  /**
   * Update progress tracker in dashboard
   */
  async function updateProgressTracker() {
    const progressData = await fetchApplicationProgress();

    if (!progressData || !progressData.stages) {
      console.error('No progress data available');
      return;
    }

    // Get user locale from localStorage or default to 'ru'
    const userProfile = localStorage.getItem('currentUserProfile');
    let locale = 'ru';
    if (userProfile) {
      try {
        const profile = JSON.parse(userProfile);
        locale = profile.locale || 'ru';
      } catch (e) {
        console.error('Error parsing user profile:', e);
      }
    }

    // Find the timeline container
    const timelineContainer = document.querySelector('.flex.flex-col.gap-6.relative.pl-6');

    if (!timelineContainer) {
      console.warn('Timeline container not found in dashboard');
      return;
    }

    // Render the timeline
    const timelineHtml = renderTimeline(progressData.stages, locale);

    // Replace the parent container content
    const parentSection = timelineContainer.parentElement;
    if (parentSection) {
      const newContent = document.createElement('div');
      newContent.innerHTML = timelineHtml;
      timelineContainer.replaceWith(newContent.firstElementChild);
    }

  }

  /**
   * Initialize progress tracker when DOM is ready
   */
  function initProgressTracker() {
    // Wait for DOM to be fully loaded
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', updateProgressTracker);
    } else {
      // DOM is already loaded
      updateProgressTracker();
    }
  }

  // Auto-initialize
  initProgressTracker();

  // Expose function globally for manual refresh
  window.refreshProgressTracker = updateProgressTracker;
})();
