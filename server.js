const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const WORKSPACE_DIR = __dirname;
const DB_PATH = path.join(WORKSPACE_DIR, 'data', 'cbse_study.db');
const DATASET_PATH = path.join(WORKSPACE_DIR, 'data', 'dataset.json');

// Load fast cached dataset
let dataset = { classes: [], prompts: [] };
if (fs.existsSync(DATASET_PATH)) {
  try {
    dataset = JSON.parse(fs.readFileSync(DATASET_PATH, 'utf-8'));
    console.log(`Loaded dataset. Total classes: ${dataset.classes.length}, Total papers: ${dataset.total_papers}`);
  } catch (err) {
    console.error('Error loading dataset.json:', err);
  }
}

// Helper: map paperId -> paper object
const paperMap = new Map();
dataset.classes.forEach(c => {
  c.subjects.forEach(s => {
    s.papers.forEach(p => {
      paperMap.set(p.id, p);
    });
  });
});

// Middleware
app.use(express.json());
app.use(express.static(path.join(WORKSPACE_DIR, 'public')));

// Serve raw PDFs directly if accessed via /papers/...
app.use('/papers', express.static(WORKSPACE_DIR));

// API 1: Classes summary
app.get('/api/classes', (req, res) => {
  const summary = dataset.classes.map(c => ({
    name: c.name,
    slug: c.slug,
    total_papers: c.total_papers,
    subject_count: c.subject_count,
    subjects: c.subjects.map(s => ({
      name: s.name,
      slug: s.slug,
      paper_count: s.paper_count,
      years_range: s.years_range,
      has_trends: s.has_trends
    }))
  }));
  res.json({ classes: summary, total_papers: dataset.total_papers });
});

// API 2: Subject detail
app.get('/api/subject/:classSlug/:subjectSlug', (req, res) => {
  const { classSlug, subjectSlug } = req.params;
  const cls = dataset.classes.find(c => c.slug === classSlug);
  if (!cls) {
    return res.status(404).json({ error: 'Class not found' });
  }
  const sub = cls.subjects.find(s => s.slug === subjectSlug);
  if (!sub) {
    return res.status(404).json({ error: 'Subject not found' });
  }

  // Generate customized prompts with [CLASS] and [SUBJECT] inserted
  const customizedPrompts = (dataset.prompts || []).map(p => {
    const text = p.template
      .replace(/\[CLASS\]/g, cls.name)
      .replace(/\[SUBJECT\]/g, sub.name);
    return {
      id: p.id,
      title: p.title,
      tagline: p.tagline,
      description: p.description,
      promptText: text
    };
  });

  res.json({
    class_name: cls.name,
    class_slug: cls.slug,
    subject_name: sub.name,
    subject_slug: sub.slug,
    paper_count: sub.paper_count,
    years_range: sub.years_range,
    years_list: sub.years_list,
    exam_types: sub.exam_types,
    sets: sub.sets,
    papers: sub.papers,
    has_trends: sub.has_trends,
    trends: sub.trends,
    question_types_observed: sub.question_types_observed,
    prompts: customizedPrompts
  });
});

// API 3: Download original PDF
app.get('/api/download/:paperId', (req, res) => {
  const { paperId } = req.params;
  const paper = paperMap.get(paperId);
  if (!paper) {
    return res.status(404).send('Question paper not found');
  }

  const fullPath = path.join(WORKSPACE_DIR, paper.file_path);
  if (!fs.existsSync(fullPath)) {
    return res.status(404).send('PDF file missing on server');
  }

  // Trigger download with genuine, clean filename
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(paper.file_name)}"`);
  const stream = fs.createReadStream(fullPath);
  stream.pipe(res);
});

// API 4: Instant Search
app.get('/api/search', (req, res) => {
  const query = (req.query.q || '').trim().toLowerCase();
  if (!query) {
    return res.json({ results: [] });
  }

  const results = [];
  dataset.classes.forEach(c => {
    c.subjects.forEach(s => {
      // 1. Match subject name
      if (s.name.toLowerCase().includes(query)) {
        results.push({
          type: 'subject',
          title: `${s.name} (${c.name})`,
          subtitle: `${s.paper_count} papers available (${s.years_range})`,
          url: `/${c.slug}/${s.slug}`,
          class_name: c.name,
          subject_name: s.name
        });
      }

      // 2. Match papers (year, qp code, exam type)
      s.papers.forEach(p => {
        const qpMatch = p.qp_code && p.qp_code.toLowerCase().includes(query);
        const yearMatch = String(p.year) === query;
        const examMatch = p.exam_type.toLowerCase().includes(query);
        if (qpMatch || (yearMatch && query.length === 4) || examMatch) {
          results.push({
            type: 'paper',
            title: `${c.name} ${s.name} - ${p.year} (${p.exam_type})`,
            subtitle: `Set ${p.set_number} | Q.P. Code: ${p.qp_code || 'N/A'} | ${p.page_count} pages`,
            url: `/${c.slug}/${s.slug}?year=${p.year}&set=${p.set_number}`,
            download_url: `/api/download/${p.id}`,
            class_name: c.name,
            subject_name: s.name,
            paper_id: p.id
          });
        }
      });

      // 3. Match trends / topics
      (s.trends || []).forEach(t => {
        if (t.topic.toLowerCase().includes(query)) {
          results.push({
            type: 'trend',
            title: `${t.topic} in ${s.name}`,
            subtitle: `Appeared in ${t.papers_count} of ${t.total_papers} papers | ${c.name}`,
            url: `/${c.slug}/${s.slug}#trends`,
            class_name: c.name,
            subject_name: s.name
          });
        }
      });
    });
  });

  // Limit to top 15 results
  res.json({ results: results.slice(0, 15) });
});

// Fallback for SPA navigation
app.use((req, res) => {
  res.sendFile(path.join(WORKSPACE_DIR, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`CBSE PYQ Study website running at http://localhost:${PORT}`);
});
