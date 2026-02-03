import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { PresetItem } from '../services/api';
import { createJob, fetchPresets } from '../services/api';
import { resolveErrorMessage, useI18n } from '../services/i18n';

const CATEGORIES = ['web', 'redes', 'ecommerce'] as const;
// Límite por job; si se excede se generan varios jobs en secuencia.
const MAX_FILES = 10;

function formatMB(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function fileKey(file: File) {
  return `${file.name}__${file.size}__${file.lastModified}`;
}

export function UploadPage() {
  const { t, presetLabel, locale } = useI18n();
  const [presetId, setPresetId] = useState('');
  const [category, setCategory] = useState<string>(CATEGORIES[0]);
  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const navigate = useNavigate();

  const totalSize = useMemo(() => files.reduce((total, file) => total + file.size, 0), [files]);
  const filteredPresets = useMemo(
    () => presets.filter((preset) => preset.category === category),
    [presets, category]
  );
  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === presetId),
    [presets, presetId]
  );

  useEffect(() => {
    const loadPresets = async () => {
      try {
        const data = await fetchPresets();
        const items = data.presets ?? [];
        setPresets(items);
        if (!presetId && items.length > 0) {
          const first = items.find((preset) => preset.category === CATEGORIES[0]) ?? items[0];
          setCategory(first.category);
          setPresetId(first.id);
        }
      } catch {
        setPresets([]);
      }
    };
    void loadPresets();
  }, []);

  useEffect(() => {
    if (!filteredPresets.length) {
      return;
    }
    if (!filteredPresets.find((preset) => preset.id === presetId)) {
      setPresetId(filteredPresets[0].id);
    }
  }, [filteredPresets, presetId]);

  const handleFiles = (incoming: FileList | null) => {
    if (!incoming) return;

    const incomingImages = Array.from(incoming).filter((file) => file.type.startsWith('image/'));
    if (!incomingImages.length) {
      setError(t.onlyImages);
      return;
    }

    let nextError = '';
    // Evita duplicados por nombre/tamaño/fecha de modificación.
    setFiles((prev) => {
      const map = new Map(prev.map((f) => [fileKey(f), f]));
      for (const f of incomingImages) map.set(fileKey(f), f);
      return Array.from(map.values());
    });

    setError(nextError);
  };

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    handleFiles(event.dataTransfer.files);
  };

  const onDragEnter = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.dataTransfer?.items?.length) {
      setDragActive(true);
    }
  };

  const onDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.currentTarget.contains(event.relatedTarget as Node)) return;
    setDragActive(false);
  };

  const onSubmit = async () => {
    if (!files.length) {
      setError(t.errorNoImages);
      return;
    }

    if (!presetId) {
      setError(t.errorSelectPreset);
      return;
    }

    setLoading(true);
    setError('');
    setInfo('');

    try {
      // Divide en lotes de MAX_FILES para mantener el límite por job.
      const chunks: File[][] = [];
      for (let i = 0; i < files.length; i += MAX_FILES) {
        chunks.push(files.slice(i, i + MAX_FILES));
      }

      for (const chunk of chunks) {
        await createJob(presetId, chunk);
      }

      if (chunks.length > 1) {
        setInfo(
          t.jobsCreatedInfo
            .replace('{jobs}', String(chunks.length))
            .replace('{images}', String(files.length)),
        );
      }
      navigate('/jobs');
    } catch (err) {
      setError(resolveErrorMessage(err, t.errorCreateJobFallback, locale));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page">
      <header className="page-header">
        <h1>{t.uploadTitle}</h1>
        <p>{t.uploadSubtitle}</p>
      </header>

      <div className="grid">
        <div
          className={`dropzone ${dragActive ? 'drag-active' : ''}`}
          onDrop={onDrop}
          onDragOver={(event) => event.preventDefault()}
          onDragEnter={onDragEnter}
          onDragLeave={onDragLeave}
        >
          <div>
            <h2>{dragActive ? t.dropActiveTitle : t.dropTitle}</h2>
            <p>{dragActive ? t.dropActiveSubtitle : t.dropSubtitle}</p>
            <input
              className="file-input"
              type="file"
              multiple
              accept="image/*"
              onChange={(event) => handleFiles(event.target.files)}
            />
          </div>
        </div>

        <div className="panel">
          <label className="label">{t.selectCategory}</label>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            {CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {presetLabel(item)}
              </option>
            ))}
          </select>

          <label className="label">{t.selectPreset}</label>
          <select value={presetId} onChange={(event) => setPresetId(event.target.value)}>
            {filteredPresets.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.label}
              </option>
            ))}
          </select>

          {selectedPreset?.density === 'suggestHigherDpi' && (
            <p className="muted">{t.suggestionSharp}</p>
          )}

          <div className="summary">
            <div>
              <span>{t.summaryFiles}</span>
              <strong>{files.length}</strong>
            </div>
            <div>
              <span>{t.summarySize}</span>
              <strong>{formatMB(totalSize)}</strong>
            </div>
          </div>

          {files.length > 0 && (
            <ul className="file-list">
              {files.map((file) => (
                <li key={fileKey(file)}>
                  <span>{file.name}</span>
                  <em>{formatMB(file.size)}</em>
                </li>
              ))}
            </ul>
          )}

          {error && <p className="error">{error}</p>}
          {info && <p className="muted">{info}</p>}

          <div className="actions-row">
            <button type="button" className="primary" onClick={onSubmit} disabled={loading}>
              {loading ? t.creatingJobs : t.process}
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setFiles([]);
                setError('');
                setInfo('');
              }}
              disabled={files.length === 0 || loading}
            >
              {t.clearFiles}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
