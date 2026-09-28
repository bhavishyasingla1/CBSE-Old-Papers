/**
 * CODJU CBSE PYQ STUDY TOOL - CLIENT APPLICATION
 * Simple, sequential 5-step flow:
 * 1. Select your class
 * 2. Select your subject
 * 3. Explore question trends
 * 4. Download question papers
 * 5. Get a subject-specific study plan
 */

(function () {
  'use strict';

  // State
  const state = {
    classesData: null,
    selectedClassSlug: null,
    selectedSubjectSlug: null,
    selectedSubjectData: null,
    filteredPapers: [],
    paperFilters: {
      year: 'all',
      exam: 'all',
      set: 'all'
    }
  };

  // DOM Elements
  const step1ClassSection = document.getElementById('step-1-class');
  const classButtonsList = document.getElementById('class-buttons-list');

  const step2SubjectSection = document.getElementById('step-2-subject');
  const subjectStepTitle = document.getElementById('subject-step-title');
  const subjectButtonsList = document.getElementById('subject-buttons-list');
  const backToClassBtn = document.getElementById('back-to-class-btn');

  const step3TrendsSection = document.getElementById('step-3-trends');
  const backToSubjectBtn = document.getElementById('back-to-subject-btn');
  const trendsSubjectSummary = document.getElementById('trends-subject-summary');
  const trendsContainer = document.getElementById('trends-container');
  const btnNextToPapers = document.getElementById('btn-next-to-papers');

  const step4PapersSection = document.getElementById('step-4-papers');
  const filterYear = document.getElementById('filter-year');
  const filterExam = document.getElementById('filter-exam');
  const filterSet = document.getElementById('filter-set');
  const filterResetBtn = document.getElementById('filter-reset-btn');
  const papersCountTag = document.getElementById('papers-count-tag');
  const papersListContainer = document.getElementById('papers-list-container');
  const btnNextToPrompts = document.getElementById('btn-next-to-prompts');

  const step5PromptsSection = document.getElementById('step-5-prompts');
  const promptsListContainer = document.getElementById('prompts-list-container');

  const toastEl = document.getElementById('toast');
  const toastTextEl = document.getElementById('toast-text');

  // ==========================================================================
  // INITIALIZATION
  // ==========================================================================

  async function init() {
    setupGlobalListeners();
    await loadClasses();
  }

  function setupGlobalListeners() {
    // Back to Step 1
    if (backToClassBtn) {
      backToClassBtn.addEventListener('click', () => {
        state.selectedClassSlug = null;
        state.selectedSubjectSlug = null;
        state.selectedSubjectData = null;

        // Hide steps 2, 3, 4, 5
        step2SubjectSection.classList.add('hidden-step');
        step3TrendsSection.classList.add('hidden-step');
        step4PapersSection.classList.add('hidden-step');
        step5PromptsSection.classList.add('hidden-step');

        // Unset active class buttons
        document.querySelectorAll('.class-card-btn').forEach(btn => btn.classList.remove('active'));

        // Scroll back to Step 1
        step1ClassSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

    // Back to Step 2 (Change Subject)
    document.querySelectorAll('.back-to-subject-action, #back-to-subject-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state.selectedSubjectSlug = null;
        state.selectedSubjectData = null;

        // Hide steps 3, 4, 5
        step3TrendsSection.classList.add('hidden-step');
        step4PapersSection.classList.add('hidden-step');
        step5PromptsSection.classList.add('hidden-step');

        // Unset active subject cards
        document.querySelectorAll('.subject-item-card').forEach(c => c.classList.remove('active'));

        // Scroll back to Step 2
        step2SubjectSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    // Smooth scroll buttons
    if (btnNextToPapers) {
      btnNextToPapers.addEventListener('click', (e) => {
        e.preventDefault();
        step4PapersSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

    if (btnNextToPrompts) {
      btnNextToPrompts.addEventListener('click', (e) => {
        e.preventDefault();
        step5PromptsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

    // Paper Filters
    if (filterYear) filterYear.addEventListener('change', handleFilterChange);
    if (filterExam) filterExam.addEventListener('change', handleFilterChange);
    if (filterSet) filterSet.addEventListener('change', handleFilterChange);
    if (filterResetBtn) {
      filterResetBtn.addEventListener('click', resetFilters);
    }
  }

  // ==========================================================================
  // STEP 1: LOAD & RENDER CLASSES
  // ==========================================================================

  async function loadClasses() {
    try {
      const res = await fetch('/api/classes');
      const data = await res.json();
      state.classesData = data;
      renderClasses();
    } catch (err) {
      console.error('Failed to load classes:', err);
    }
  }

  function renderClasses() {
    if (!state.classesData || !state.classesData.classes) return;

    classButtonsList.innerHTML = state.classesData.classes.map(c => `
      <button class="class-card-btn ${state.selectedClassSlug === c.slug ? 'active' : ''}" data-class-slug="${c.slug}" type="button">
        <div>
          <div class="class-btn-title">${escapeHtml(c.name)}</div>
          <div class="class-btn-sub">${c.total_papers} Papers &bull; ${c.subject_count} Subjects</div>
        </div>
        <div class="class-btn-arrow">&rarr;</div>
      </button>
    `).join('');

    classButtonsList.querySelectorAll('.class-card-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const slug = btn.getAttribute('data-class-slug');
        selectClass(slug);
      });
    });
  }

  function selectClass(slug) {
    state.selectedClassSlug = slug;

    // Update active style on cards
    classButtonsList.querySelectorAll('.class-card-btn').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-class-slug') === slug);
    });

    // Close downstream steps if class changed
    state.selectedSubjectSlug = null;
    state.selectedSubjectData = null;
    step3TrendsSection.classList.add('hidden-step');
    step4PapersSection.classList.add('hidden-step');
    step5PromptsSection.classList.add('hidden-step');

    // Reveal Step 2
    renderSubjectsForClass(slug);
    step2SubjectSection.classList.remove('hidden-step');

    // Smooth scroll to Step 2
    setTimeout(() => {
      step2SubjectSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  }

  // ==========================================================================
  // STEP 2: LOAD & RENDER SUBJECTS
  // ==========================================================================

  function renderSubjectsForClass(classSlug) {
    const classObj = state.classesData.classes.find(c => c.slug === classSlug);
    if (!classObj) return;

    subjectStepTitle.textContent = `Select your ${classObj.name} subject`;

    subjectButtonsList.innerHTML = classObj.subjects.map(s => `
      <div class="subject-item-card ${state.selectedSubjectSlug === s.slug ? 'active' : ''}" data-subject-slug="${s.slug}">
        <div class="subj-name">${escapeHtml(s.name)}</div>
        <div class="subj-meta-row">
          <span>${s.paper_count} Papers (${s.years_range})</span>
          ${s.has_trends ? '<span class="trend-green-tag">&#x2713; Trends</span>' : ''}
        </div>
      </div>
    `).join('');

    subjectButtonsList.querySelectorAll('.subject-item-card').forEach(card => {
      card.addEventListener('click', () => {
        const subSlug = card.getAttribute('data-subject-slug');
        selectSubject(subSlug);
      });
    });
  }

  async function selectSubject(subSlug) {
    state.selectedSubjectSlug = subSlug;

    // Highlight active card
    subjectButtonsList.querySelectorAll('.subject-item-card').forEach(c => {
      c.classList.toggle('active', c.getAttribute('data-subject-slug') === subSlug);
    });

    try {
      const res = await fetch(`/api/subject/${state.selectedClassSlug}/${subSlug}`);
      if (!res.ok) throw new Error('Subject fetch failed');
      const data = await res.json();
      state.selectedSubjectData = data;

      // Populate Steps 3, 4, 5
      renderStep3Trends(data);
      setupStep4Papers(data);
      renderStep5Prompts(data);

      // Reveal Steps 3, 4, 5
      step3TrendsSection.classList.remove('hidden-step');
      step4PapersSection.classList.remove('hidden-step');
      step5PromptsSection.classList.remove('hidden-step');

      // Smooth scroll to Step 3
      setTimeout(() => {
        step3TrendsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);

    } catch (err) {
      console.error('Error loading subject details:', err);
    }
  }

  // ==========================================================================
  // STEP 3: EXPLORE QUESTION TRENDS
  // ==========================================================================

  function renderStep3Trends(data) {
    // Subject Summary Header + Sleek Quick Jump Navigation
    trendsSubjectSummary.innerHTML = `
      <div style="width: 100%;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem;">
          <div class="summary-subject-title">${escapeHtml(data.subject_name)}</div>
          <span class="sum-badge purple">${escapeHtml(data.class_name)} &bull; ${data.paper_count} Papers (${data.years_range})</span>
        </div>

        <div class="subject-quick-nav">
          <button class="quick-nav-btn" type="button" id="quick-jump-trends">
            <span class="nav-icon">&#x1F4CA;</span>
            <span>Question Trends</span>
          </button>
          <button class="quick-nav-btn" type="button" id="quick-jump-papers">
            <span class="nav-icon">&#x1F4E5;</span>
            <span>Download PYQs (${data.paper_count})</span>
          </button>
          <button class="quick-nav-btn" type="button" id="quick-jump-prompts">
            <span class="nav-icon">&#x1F916;</span>
            <span>AI Study Prompts</span>
          </button>
        </div>
      </div>
    `;

    // Wire quick jump buttons
    document.getElementById('quick-jump-trends').addEventListener('click', () => {
      step3TrendsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    document.getElementById('quick-jump-papers').addEventListener('click', () => {
      step4PapersSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    document.getElementById('quick-jump-prompts').addEventListener('click', () => {
      step5PromptsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // Topic Cards with expandable question drawer
    const topicCardsHtml = (data.trends || []).map((t, idx) => {
      const qListHtml = (t.supporting_questions || []).map(q => `
        <div class="q-evidence-item">
          <span class="q-evidence-tag">${q.year} Q${q.question_number} (${q.marks || 1}M):</span>
          <span>${escapeHtml(q.snippet || '')}</span>
        </div>
      `).join('');

      return `
        <div class="trend-card-unit" data-trend-id="${t.id}">
          <div class="unit-head-row">
            <span class="unit-title">${escapeHtml(t.topic)}</span>
            <span class="unit-freq-pill">In ${t.papers_count} of ${t.total_papers} papers</span>
          </div>

          <div class="unit-stats-line">
            Years: <strong>${t.years_seen.join(', ')}</strong> &bull; Types: <strong>${t.question_types.join(', ')}</strong>
          </div>

          <div class="btn-toggle-evidence" data-target="drawer-${idx}">
            <span>View questions (${(t.supporting_questions || []).length})</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="m6 9 6 6 6-6"/>
            </svg>
          </div>

          <div class="unit-evidence-drawer" id="drawer-${idx}">
            ${qListHtml}
          </div>
        </div>
      `;
    }).join('');

    // Tick Matrix Table ("Appearance by Year")
    const allYears = data.years_list || [];
    const matrixRowsHtml = (data.trends || []).map(t => {
      const yearCells = allYears.map(yr => {
        const has = t.years_seen.includes(String(yr));
        return `<td style="text-align: center;">${has ? '<span class="tick-green">&#x2713;</span>' : '<span class="tick-dash">&mdash;</span>'}</td>`;
      }).join('');

      return `
        <tr>
          <td>${escapeHtml(t.topic)}</td>
          ${yearCells}
        </tr>
      `;
    }).join('');

    const matrixHtml = `
      <div class="trend-matrix-wrapper">
        <div class="matrix-header-title">Appearance by Year</div>
        <table class="tick-table">
          <thead>
            <tr>
              <th>Topic</th>
              ${allYears.map(y => `<th>${y}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${matrixRowsHtml}
          </tbody>
        </table>
      </div>
    `;

    // Priority Box
    const topTrend = (data.trends && data.trends.length > 0) ? data.trends[0] : null;
    const priorityHtml = topTrend ? `
      <div class="priority-callout">
        <div class="priority-callout-title">Worth practising first:</div>
        <div class="priority-callout-desc">${escapeHtml(topTrend.topic)} (appeared in ${topTrend.papers_count} papers across ${topTrend.years_seen.length} years).</div>
      </div>
    ` : '';

    trendsContainer.innerHTML = topicCardsHtml + matrixHtml + priorityHtml;

    // Attach drawer toggles
    trendsContainer.querySelectorAll('.btn-toggle-evidence').forEach(btn => {
      btn.addEventListener('click', () => {
        const drawerId = btn.getAttribute('data-target');
        const drawer = document.getElementById(drawerId);
        if (drawer) {
          const isOpen = drawer.classList.toggle('show');
          btn.classList.toggle('open', isOpen);
        }
      });
    });
  }

  // ==========================================================================
  // STEP 4: DOWNLOAD QUESTION PAPERS
  // ==========================================================================

  function setupStep4Papers(data) {
    // Populate filter dropdowns
    filterYear.innerHTML = '<option value="all">All Years</option>' +
      (data.years_list || []).map(y => `<option value="${y}">${y}</option>`).join('');

    filterExam.innerHTML = '<option value="all">All Exams</option>' +
      (data.exam_types || []).map(e => `<option value="${escapeHtml(e)}">${escapeHtml(e)}</option>`).join('');

    filterSet.innerHTML = '<option value="all">All Sets</option>' +
      (data.sets || []).map(s => `<option value="${escapeHtml(s)}">Set ${escapeHtml(s)}</option>`).join('');

    state.paperFilters = { year: 'all', exam: 'all', set: 'all' };
    filterYear.value = 'all';
    filterExam.value = 'all';
    filterSet.value = 'all';

    renderPapersList();
  }

  function handleFilterChange() {
    state.paperFilters.year = filterYear.value;
    state.paperFilters.exam = filterExam.value;
    state.paperFilters.set = filterSet.value;
    renderPapersList();
  }

  function resetFilters() {
    filterYear.value = 'all';
    filterExam.value = 'all';
    filterSet.value = 'all';
    state.paperFilters = { year: 'all', exam: 'all', set: 'all' };
    renderPapersList();
  }

  function renderPapersList() {
    if (!state.selectedSubjectData || !state.selectedSubjectData.papers) return;

    const all = state.selectedSubjectData.papers;
    const { year, exam, set } = state.paperFilters;

    const filtered = all.filter(p => {
      const matchY = year === 'all' || String(p.year) === year;
      const matchE = exam === 'all' || p.exam_type === exam;
      const matchS = set === 'all' || p.set_number === set;
      return matchY && matchE && matchS;
    });

    state.filteredPapers = filtered;
    papersCountTag.textContent = `Showing ${filtered.length} of ${all.length} papers`;

    if (filtered.length === 0) {
      papersListContainer.innerHTML = `
        <div style="padding: 2rem; text-align: center; color: var(--text-muted); font-size: 0.9rem;">
          No question papers match the selected filters.
          <div style="margin-top: 0.5rem;">
            <button class="filter-reset-action" onclick="document.getElementById('filter-reset-btn').click()">Reset Filters</button>
          </div>
        </div>
      `;
      return;
    }

    papersListContainer.innerHTML = filtered.map(p => `
      <div class="single-paper-card">
        <div class="paper-left-block">
          <div class="paper-year-huge">${p.year}</div>
          <div class="paper-meta-column">
            <div class="paper-exam-name">${escapeHtml(p.exam_type)}</div>
            <div class="paper-tags-row">
              <span class="paper-tag-pill">Set ${escapeHtml(p.set_number)}</span>
              ${p.qp_code ? `<span class="paper-tag-pill qp">QP: ${escapeHtml(p.qp_code)}</span>` : ''}
              <span class="paper-tag-pill">${p.page_count} pages</span>
            </div>
          </div>
        </div>

        <a href="${p.download_url}" class="btn-download-pdf-clean" download="${escapeHtml(p.file_name)}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          <span>Download PDF</span>
        </a>
      </div>
    `).join('');
  }

  // ==========================================================================
  // STEP 5: SUBJECT-SPECIFIC DETAILED AI STUDY PROMPTS
  // ==========================================================================

  function renderStep5Prompts(data) {
    const className = data.class_name || 'Class 10';
    const subjectName = data.subject_name || 'Subject';
    const paperCount = data.paper_count || 5;
    const yearsRange = data.years_range || '2022–2026';

    // Extract verified recurring topics if available
    let recurringTopicsSummary = '';
    if (data.has_trends && data.trends && data.trends.length > 0) {
      recurringTopicsSummary = data.trends.map((t, i) => `${i + 1}. ${t.topic} (Appeared in ${t.papers_count} papers; styles: ${t.question_types.join(', ')})`).join('\n');
    }

    // 5 Deeply detailed, subject-specific study prompts
    const prompts = [
      {
        id: 'topic-by-topic-tutor',
        title: '1. Topic-by-Topic Master Tutor (One by One)',
        tagline: 'Learn each core concept sequentially with interactive checkpoints.',
        purpose: 'Guides the AI to explain important topics one by one. The AI will explain the theory, show past CBSE question styles, and test you before moving to the next concept.',
        promptText: `I am preparing for CBSE ${className} ${subjectName}.

I have uploaded ${paperCount} previous-year CBSE question papers (${yearsRange}).
${recurringTopicsSummary ? `\nVerified high-frequency topics observed from these papers:\n${recurringTopicsSummary}\n` : ''}
Act as my expert CBSE tutor for ${subjectName}.

Your goal is to teach me the essential concepts ONE BY ONE. Do not overwhelm me with everything at once.

Follow these strict rules:

1. START WITH TOPIC 1:
   - Explain the concept in crystal-clear language with simple real-world examples.
   - Summarize the key definitions, principles, and points I must write to get full marks.
   - Show 1–2 exact ways this topic was tested in the uploaded question papers.
   - Point out common traps, confusing terms, and mistakes students make.

2. INTERACTIVE CHECKPOINT:
   - Ask me ONE exam-style question on this topic.
   - Wait for my response before proceeding.

3. EVALUATE MY ANSWER:
   - When I respond, tell me what I got right, what keywords I missed, and what marks out of 2 or 3 I would receive.
   - If my answer is weak, explain the concept again simply.
   - If my answer is solid, ask me if I am ready to move to Topic 2.

Proceed topic by topic until we cover the high-frequency areas of ${subjectName}.`
      },
      {
        id: 'cbse-marking-evaluator',
        title: '2. CBSE Official Marking Scheme Evaluator',
        tagline: 'Get your answers scored according to official CBSE board standards.',
        purpose: 'Paste your written answer alongside a question. The AI checks keyword inclusion, step-wise mark distribution, and provides a 100% full-mark model answer.',
        promptText: `I am preparing for CBSE ${className} ${subjectName}.

Act as a strict, experienced CBSE Board Examiner.

I will provide:
1. Question from a previous year paper (with marks allotted)
2. My written answer

Evaluate my answer strictly according to official CBSE marking guidelines:

Format your feedback as:
- [MARKS AWARDED]: e.g., 2.5 / 3 Marks
- [KEYWORD AUDIT]: List which mandatory technical terms I included and which required terms I missed.
- [POINT-BY-POINT ANALYSIS]: What part of the answer earned marks and what was vague or incorrect.
- [STEP-WISE DEDUCTION]: Explain why any marks were deducted.
- [FULL-MARKS MODEL ANSWER]: Write the exact, bulleted answer that guarantees full marks from a CBSE evaluator.

Here is my first question and answer:
[PASTE QUESTION AND YOUR ANSWER HERE]`
      },
      {
        id: 'high-yield-traps-drill',
        title: '3. High-Yield PYQs & Common Traps Drill',
        tagline: 'Master tricky questions and recurring question patterns.',
        purpose: 'Focuses on the questions that appear repeatedly and highlights tricky phrasing, confusing options in MCQs, and subtle conceptual differences.',
        promptText: `I am preparing for CBSE ${className} ${subjectName}.

I have uploaded my CBSE previous-year question papers.

Analyze the uploaded papers and identify:
1. Questions or concepts that appeared repeatedly across multiple years.
2. Tricky MCQs or application questions where students commonly lose marks.
3. Subtle distinctions between commonly confused terms in ${subjectName}.

Now drill me with 5 high-yield practice scenarios based strictly on the style and difficulty of the uploaded papers:
- Present Question 1 first.
- Do NOT provide the answer immediately.
- Wait for my answer, score it, provide the ideal CBSE presentation points, and then give Question 2.`
      },
      {
        id: 'five-day-revision-sprint',
        title: '4. 5-Day Subject Revision Sprint',
        tagline: 'Structured day-by-day study roadmap prioritizing high-frequency topics.',
        purpose: 'Creates a realistic, high-efficiency 5-day study plan covering recurring topics first, with exact daily study tasks and question practice.',
        promptText: `I am preparing for CBSE ${className} ${subjectName} and I have 5 days left to revise.

I have uploaded my previous-year question papers (${yearsRange}).

Create a structured 5-Day Revision Roadmap for me:

For each day (Day 1 through Day 5), tell me:
1. Morning Session: Which high-frequency topics to review and key formulas/definitions to memorize.
2. Afternoon Session: Specific question types and PYQ questions to practice under timed conditions.
3. Evening Session: Quick self-quiz checkpoint and weak area remediation.

Rules:
- Prioritize topics that appeared repeatedly across the uploaded papers.
- Balance theory revision with active question writing.
- Keep the daily workload realistic for a high school student.`
      },
      {
        id: 'cbse-mock-paper-generator',
        title: '5. Fresh CBSE Pattern Mock Test Generator',
        tagline: 'Generate an authentic new practice paper matching official CBSE patterns.',
        purpose: 'Generates a fresh mock test with Section A (1M), Section B (2M), Section C (3-4M), and case-based questions matching recent board exam layouts.',
        promptText: `I am preparing for CBSE ${className} ${subjectName}.

I have uploaded my previous-year question papers.

Generate a FRESH practice test that follows the exact structure and difficulty level of the latest uploaded CBSE paper.

Requirements:
- Mirror the official section layout (MCQs, Short Answer, Long Answer, Case Study).
- Test similar core concepts and cognitive levels without copying the exact question text.
- Provide the questions first.
- At the very end, include a comprehensive Marking Scheme with point-by-point answer keys and step marks.`
      }
    ];

    promptsListContainer.innerHTML = prompts.map(p => `
      <div class="prompt-study-card">
        <div class="prompt-card-header-row">
          <div>
            <div class="prompt-card-title">${escapeHtml(p.title)}</div>
            <div class="prompt-tagline">${escapeHtml(p.tagline)}</div>
          </div>

          <button class="btn-copy-study-prompt" data-prompt-id="${p.id}" type="button">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <span>Copy Prompt</span>
          </button>
        </div>

        <div class="prompt-purpose">${escapeHtml(p.purpose)}</div>
        <pre class="prompt-code-full" id="prompt-text-${p.id}">${escapeHtml(p.promptText)}</pre>
      </div>
    `).join('');

    // Wire copy buttons
    promptsListContainer.querySelectorAll('.btn-copy-study-prompt').forEach(btn => {
      btn.addEventListener('click', async () => {
        const pid = btn.getAttribute('data-prompt-id');
        const codeEl = document.getElementById(`prompt-text-${pid}`);
        if (!codeEl) return;

        const text = codeEl.textContent;

        try {
          await navigator.clipboard.writeText(text);
          btn.classList.add('copied');
          btn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>Copied!</span>
          `;

          showToast('Prompt copied to clipboard! Paste it into your AI.');

          setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = `
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              <span>Copy Prompt</span>
            `;
          }, 2200);
        } catch (err) {
          console.error('Clipboard copy failed:', err);
        }
      });
    });
  }

  // ==========================================================================
  // UTILITIES
  // ==========================================================================

  function showToast(msg) {
    toastTextEl.textContent = msg;
    toastEl.classList.add('show');
    setTimeout(() => {
      toastEl.classList.remove('show');
    }, 2500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  init();
})();
