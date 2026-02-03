import { useEffect, useMemo, useState, useCallback } from 'react';
import { Link, useParams } from 'react-router-dom';

import type { JobDetail, JobFileReport, PresetItem } from '../services/api';
import {
  buildDownloadUrl,
  fetchPresets,
  getJob,
  reprocessFile,
  updateJobFile,
  type JobFileUpdatePayload,
} from '../services/api';
import { resolveErrorMessage, useI18n } from '../services/i18n';
import { CropModal } from '../components/CropModal';

function formatSize(bytes: number | null | undefined) {
  if (bytes === null || bytes === undefined) return '-';
  const mb = bytes / 1024 / 1024;
  if (mb >= 1) return `${mb.toFixed(2)} MB`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export function JobDetailPage() {
  const { id } = useParams();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [naming, setNaming] = useState<{ pattern?: string; normalize?: Record<string, unknown> }>({});
  const [fileEdits, setFileEdits] = useState<Record<number, JobFileUpdatePayload>>({});
  const [cropFileId, setCropFileId] = useState<number | null>(null);
  const [openFileId, setOpenFileId] = useState<number | null>(null);
  // Preferencias de snippet persistidas localmente.
  const [basePath, setBasePath] = useState(() => {
    return localStorage.getItem('snippetBasePath') || '/img/';
  });
  const [copied, setCopied] = useState('');
  const { t, presetLabel, statusLabel, locale } = useI18n();

  const loadJob = useCallback(async () => {
    if (!id) return;

    try {
      const data = await getJob(Number(id));
      setJob(data);
      setError('');
      setInfo('');
    } catch (err) {
      setError(resolveErrorMessage(err, t.errorLoadJob, locale));
    }
  }, [id, t.errorLoadJob]);

  useEffect(() => {
    void loadJob();
    // Polling para mantener estado y progreso en tiempo real.
    const interval = setInterval(() => void loadJob(), 4000);
    return () => clearInterval(interval);
  }, [loadJob]);

  useEffect(() => {
    const loadPresets = async () => {
      try {
        const data = await fetchPresets();
        setPresets(data.presets ?? []);
        setNaming(data.naming ?? {});
      } catch {
        setPresets([]);
      }
    };
    void loadPresets();
  }, []);

  useEffect(() => {
    localStorage.setItem('snippetBasePath', basePath);
  }, [basePath]);

  const presetsMap = useMemo(() => {
    return presets.reduce<Record<string, PresetItem>>((acc, preset) => {
      acc[preset.id] = preset;
      return acc;
    }, {});
  }, [presets]);

  const isFinished = job ? job.status !== 'PROCESSING' && job.status !== 'PENDING' : false;
  const cropFile = job?.files.find((file) => file.id === cropFileId) ?? null;
  const presetInfo = presetsMap[job?.preset ?? ''];
  const presetCategory = presetInfo?.category;

  const presetOptions = useMemo(() => {
    const filtered = presetCategory
      ? presets.filter((preset) => preset.category === presetCategory)
      : presets;
    return filtered.length ? filtered : presets;
  }, [presetCategory, presets]);

  const handleEditChange = (fileId: number, patch: JobFileUpdatePayload) => {
    setFileEdits((current) => ({
      ...current,
      [fileId]: {
        ...current[fileId],
        ...patch,
      },
    }));
  };

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>{t.jobDetailTitle}</h1>
          <p>{t.jobDetailSubtitle}</p>
        </div>
        <div className="actions">
          <Link className="ghost" to="/jobs">
            {t.backToJobs}
          </Link>

          {job && isFinished && (
            <a className="primary" href={buildDownloadUrl(job.id)}>
              {t.downloadZip}
            </a>
          )}
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      {info && <p className="muted">{info}</p>}
      {copied && <p className="muted">{copied}</p>}
      {job?.error_message && <p className="error">{job.error_message}</p>}
      {job &&
        job.status === 'FAILED' &&
        job.files?.some((file) => file.status === 'DONE') && (
          <p className="error">{t.partialFailures}</p>
        )}

      {job && (
        <div className="detail-grid">
          <div className="panel">
            <h2>{t.summary}</h2>
            <ul className="summary-list">
              <li>
                <span>{t.tableStatus}</span>
                <strong className={`status ${job.status.toLowerCase()}`}>
                  {statusLabel(job.status)}
                </strong>
              </li>
              <li>
                <span>{t.tablePreset}</span>
                <strong>{presetsMap[job.preset]?.label ?? presetLabel(job.preset)}</strong>
              </li>
              <li>
                <span>{t.tableProgress}</span>
                <strong>{job.progress ?? 0}%</strong>
              </li>
              <li>
                <span>{t.tableFiles}</span>
                <strong>
                  {job.processed_files ?? 0}/{job.total_files ?? 0}
                </strong>
              </li>
            </ul>
          </div>

          <div className="panel">
            <h2>{t.preview}</h2>
            <div className="snippet-tools">
              <label>
                {t.snippetBase}
                <input
                  type="text"
                  value={basePath}
                  onChange={(event) => setBasePath(event.target.value)}
                />
              </label>
              <button
                className="ghost"
                type="button"
                onClick={async () => {
                  if (!job?.files?.length) return;
                  const snippets = job.files
                    .filter((file) => file.output_name)
                    .map((file) => buildSnippet(file, basePath, presetsMap, job));
                  await navigator.clipboard.writeText(snippets.join('\n'));
                  setCopied(t.snippetCopied);
                  setTimeout(() => setCopied(''), 2000);
                }}
              >
                {t.snippetAll}
              </button>
              <span className="muted">{t.snippetAdvanced}</span>
            </div>
            <div className="file-cards">
              {(job.files ?? []).map((file) => (
                <div className="file-card" key={file.id}>
                  {(() => {
                    // Deriva ajustes efectivos y banderas de cambio para cada archivo.
                    const edits = fileEdits[file.id] ?? {};
                    const effectivePresetId =
                      edits.selected_preset_id ??
                      file.selected_preset_id ??
                      job.preset ??
                      file.recommended_preset_id ??
                      presetOptions[0]?.id ??
                      '';
                    const allowedFormats = ['webp', 'jpg', 'png'];
                    const recommendedFormats = (file.recommended_formats ?? []).filter((fmt) =>
                      allowedFormats.includes(fmt),
                    );
                    const storedFormats = (file.output_formats ?? []).filter((fmt) =>
                      allowedFormats.includes(fmt),
                    );
                    const baseFormats = storedFormats.length
                      ? storedFormats
                      : recommendedFormats.length
                      ? recommendedFormats
                      : [file.output_format ?? 'webp'].filter((fmt) => allowedFormats.includes(fmt));
                    const effectiveFormatsRaw = edits.output_formats ?? baseFormats;
                    const effectiveFormats = effectiveFormatsRaw.length ? effectiveFormatsRaw : baseFormats;
                    const basePrimaryFormat = file.output_format ?? baseFormats[0] ?? 'webp';
                    const preferredPrimary = edits.output_format ?? basePrimaryFormat;
                    const primaryFormat = effectiveFormats.includes(preferredPrimary)
                      ? preferredPrimary
                      : effectiveFormats[0] ?? preferredPrimary ?? 'webp';
                    const recommendedQuality = file.recommended_quality ?? {};
                    const baseWebpQuality = Number(file.quality_webp ?? recommendedQuality.webp ?? 80);
                    const baseJpgQuality = Number(file.quality_jpg ?? recommendedQuality.jpg ?? 82);
                    const webpQuality = edits.quality_webp ?? file.quality_webp ?? baseWebpQuality;
                    const jpgQuality = edits.quality_jpg ?? file.quality_jpg ?? baseJpgQuality;
                    const baseRemoveMetadata = !(file.keep_metadata ?? false);
                    const removeMetadata =
                      edits.keep_metadata !== undefined ? !edits.keep_metadata : baseRemoveMetadata;
                    const baseKeepTransparency = file.keep_transparency ?? true;
                    const keepTransparency =
                      edits.keep_transparency !== undefined ? edits.keep_transparency : baseKeepTransparency;
                    const renamePattern =
                      edits.rename_pattern ?? file.rename_pattern ?? naming.pattern ?? '{name-normalized}.{ext}';
                    const normalizeLowercase =
                      edits.normalize_lowercase ?? file.normalize_lowercase ?? true;
                    const normalizeRemoveAccents =
                      edits.normalize_remove_accents ?? file.normalize_remove_accents ?? true;
                    const normalizeReplaceSpaces =
                      edits.normalize_replace_spaces ?? file.normalize_replace_spaces ?? '-';
                    const normalizeCollapseDashes =
                      edits.normalize_collapse_dashes ?? file.normalize_collapse_dashes ?? true;
                    const basePresetId =
                      file.selected_preset_id ??
                      job.preset ??
                      file.recommended_preset_id ??
                      presetOptions[0]?.id ??
                      '';
                    const baseRenamePattern = file.rename_pattern ?? naming.pattern ?? '{name-normalized}.{ext}';
                    const baseNormalizeLowercase = file.normalize_lowercase ?? true;
                    const baseNormalizeRemoveAccents = file.normalize_remove_accents ?? true;
                    const baseNormalizeReplaceSpaces = file.normalize_replace_spaces ?? '-';
                    const baseNormalizeCollapseDashes = file.normalize_collapse_dashes ?? true;
                    const baseCropEnabled = file.crop_enabled ?? false;
                    const baseCropX = file.crop_x ?? null;
                    const baseCropY = file.crop_y ?? null;
                    const baseCropW = file.crop_w ?? null;
                    const baseCropH = file.crop_h ?? null;
                    const namePreview = buildNamePreview(
                      file.original_name,
                      effectivePresetId,
                      primaryFormat,
                      renamePattern,
                      normalizeLowercase,
                      normalizeRemoveAccents,
                      normalizeReplaceSpaces,
                      normalizeCollapseDashes,
                    );
                    const effectivePreset = presetsMap[effectivePresetId];
                    const effectivePresetOrientation = effectivePreset
                      ? detectOrientation(effectivePreset.width, effectivePreset.height)
                      : null;
                    const shouldAutoCrop =
                      Boolean(edits.selected_preset_id) &&
                      Boolean(effectivePresetOrientation) &&
                      Boolean(file.orientation) &&
                      effectivePresetOrientation !== file.orientation;
                    const cropEnabled =
                      edits.crop_enabled !== undefined ? edits.crop_enabled : file.crop_enabled ?? false;
                    const targetWidth = effectivePreset?.width;
                    const targetHeight = effectivePreset?.height;
                    const noUpscaleWarning =
                      targetWidth &&
                      targetHeight &&
                      file.original_width &&
                      file.original_height &&
                      (file.original_width < targetWidth || file.original_height < targetHeight);
                    const outputsSummary = buildOutputsSummary(file.output_variants);
                    const has2x = Boolean(
                      file.output_variants?.some((variant) => variant.scale === '2x'),
                    );
                    const widthBefore = file.width_before ?? file.original_width;
                    const heightBefore = file.height_before ?? file.original_height;
                    const widthAfter = file.width_after ?? file.output_width;
                    const heightAfter = file.height_after ?? file.output_height;
                    const cropped = file.cropped ?? file.crop_enabled ?? false;
                    const metadataRemoved =
                      file.metadata_removed ?? (file.keep_metadata === undefined ? true : !file.keep_metadata);
                    const baseOutputFormats = baseFormats;
                    const formatsDirty = !arraysEqual(baseOutputFormats, effectiveFormats);
                    const basePrimary = basePrimaryFormat;
                    const primaryDirty = basePrimary !== primaryFormat;
                    const webpDirty =
                      effectiveFormats.includes('webp') && Number(baseWebpQuality) !== Number(webpQuality);
                    const jpgDirty =
                      effectiveFormats.includes('jpg') && Number(baseJpgQuality) !== Number(jpgQuality);
                    const qualityDirty = webpDirty || jpgDirty;
                    const baseGenerate2x = file.generate_2x ?? false;
                    const baseGenerateSharpened = file.generate_sharpened ?? false;
                    const generate2x =
                      edits.generate_2x !== undefined ? edits.generate_2x : baseGenerate2x;
                    const generateSharpened =
                      edits.generate_sharpened !== undefined ? edits.generate_sharpened : baseGenerateSharpened;
                    const sharpRecommended = effectivePreset?.density === 'suggestHigherDpi';

                    const isDirty =
                      basePresetId !== effectivePresetId ||
                      formatsDirty ||
                      primaryDirty ||
                      qualityDirty ||
                      baseRemoveMetadata !== removeMetadata ||
                      baseKeepTransparency !== keepTransparency ||
                      baseRenamePattern !== renamePattern ||
                      baseNormalizeLowercase !== normalizeLowercase ||
                      baseNormalizeRemoveAccents !== normalizeRemoveAccents ||
                      baseNormalizeReplaceSpaces !== normalizeReplaceSpaces ||
                      baseNormalizeCollapseDashes !== normalizeCollapseDashes ||
                      baseCropEnabled !== cropEnabled ||
                      baseCropX !== (edits.crop_x ?? baseCropX) ||
                      baseCropY !== (edits.crop_y ?? baseCropY) ||
                      baseCropW !== (edits.crop_w ?? baseCropW) ||
                      baseCropH !== (edits.crop_h ?? baseCropH) ||
                      baseGenerate2x !== generate2x ||
                      baseGenerateSharpened !== generateSharpened;
                    const presetDirty = basePresetId !== effectivePresetId;
                    const formatDirty = formatsDirty || primaryDirty;
                    const metadataDirty = baseRemoveMetadata !== removeMetadata;
                    const transparencyDirty = baseKeepTransparency !== keepTransparency;
                    const nameDirty =
                      baseRenamePattern !== renamePattern ||
                      baseNormalizeLowercase !== normalizeLowercase ||
                      baseNormalizeRemoveAccents !== normalizeRemoveAccents ||
                      baseNormalizeReplaceSpaces !== normalizeReplaceSpaces ||
                      baseNormalizeCollapseDashes !== normalizeCollapseDashes;
                    const cropDirty =
                      baseCropEnabled !== cropEnabled ||
                      baseCropX !== (edits.crop_x ?? baseCropX) ||
                      baseCropY !== (edits.crop_y ?? baseCropY) ||
                      baseCropW !== (edits.crop_w ?? baseCropW) ||
                      baseCropH !== (edits.crop_h ?? baseCropH);

                    return (
                      <>
                        <div className="file-card-header">
                          <div>
                            <strong>{file.original_name}</strong>
                            <div className="muted">
                              {t.originalSizeLabel}: {formatSize(file.original_size)} · {t.optimizedSizeLabel}:{' '}
                              {formatSize(file.output_size)}
                            </div>
                          </div>
                          <div className="file-actions">
                            <button
                              className="ghost"
                              type="button"
                              onClick={async () => {
                                if (!file.output_name) return;
                                const snippet = buildSnippet(file, basePath, presetsMap, job);
                                await navigator.clipboard.writeText(snippet);
                                setCopied(t.snippetCopied);
                                setTimeout(() => setCopied(''), 2000);
                              }}
                            >
                              {t.copySnippet}
                            </button>
                          </div>
                        </div>
                        <div className="file-previews">
                          <div className="preview-block">
                            <span className="label">{t.original}</span>
                            {file.original_url ? (
                              <div
                                className="thumb-frame"
                                style={{
                                  aspectRatio: buildAspectRatio(file.original_width, file.original_height),
                                }}
                              >
                                <img className="thumb" src={file.original_url} alt={file.original_name} />
                              </div>
                            ) : (
                              <span className="muted">{t.notAvailable}</span>
                            )}
                            <div className="file-meta">
                              <span>
                                {t.dimsBefore}:{' '}
                                {widthBefore && heightBefore ? `${widthBefore}×${heightBefore}` : '-'}
                              </span>
                              <span>
                                {t.orientationLabel}: {file.orientation ?? '-'} · {t.aspectLabel}: {file.aspect_label ?? '-'}
                              </span>
                              <span>
                                {t.transparencyLabel}:{' '}
                                {file.has_transparency === true ? t.yes : file.has_transparency === false ? t.no : '-'}
                              </span>
                              <span>
                                {t.typeLabel}:{' '}
                                {file.analysis_type === 'ui' ? 'UI' : file.analysis_type === 'photo' ? t.photoLabel : '-'}
                              </span>
                              <span>
                                {t.metadataRemoved}: {metadataRemoved ? t.yes : t.no}
                              </span>
                            </div>
                          </div>
                          <div className="preview-block">
                            <span className="label">{t.optimized}</span>
                            {file.output_url ? (
                              <div
                                className="thumb-frame"
                                style={{
                                  aspectRatio: parseAspect(effectivePreset?.aspect ?? '1:1'),
                                }}
                              >
                                <img className="thumb" src={file.output_url} alt={file.output_name ?? ''} />
                              </div>
                            ) : (
                              <span className="muted">{t.notReady}</span>
                            )}
                            <div className="file-meta">
                              <span>
                                {t.dimsAfter}:{' '}
                                {widthAfter && heightAfter ? `${widthAfter}×${heightAfter}` : '-'}
                              </span>
                              <span>
                                {t.reduction}:{' '}
                                {file.reduction_percent !== null ? `${file.reduction_percent}%` : '-'}
                              </span>
                              <span>
                                {t.primaryFormat}: {file.final_format ?? primaryFormat ?? '-'}
                                {has2x && <span className="badge">+2x</span>}
                              </span>
                              <span>
                                {t.outputsGenerated}: {outputsSummary}
                              </span>
                              <span>
                                {t.cropped}: {cropped ? t.yes : t.no}
                              </span>
                              <span>
                                {t.finalFormat}: {file.final_format ?? primaryFormat ?? '-'}
                              </span>
                              <span>
                                {t.status}: {statusLabel(file.status)}
                              </span>
                              {file.status === 'FAILED' && file.error_message && (
                                <span className="error">{file.error_message}</span>
                              )}
                            </div>
                            <div className="file-settings-accordion">
                              <button
                                type="button"
                                className={`accordion-toggle ${openFileId === file.id ? 'open' : ''}`}
                                onClick={() =>
                                  setOpenFileId((current) => (current === file.id ? null : file.id))
                                }
                              >
                                <span className="accordion-icon">
                                  {openFileId === file.id ? '▾' : '▸'}
                                </span>
                                <span className="accordion-title">{t.fileSettings}</span>
                                {isDirty && <span className="accordion-dirty">● {t.unsavedChanges}</span>}
                              </button>
                              <div className={`accordion-panel ${openFileId === file.id ? 'open' : ''}`}>
                                <div className="file-settings">
                                  <div className="settings-grid">
                                    <label className={presetDirty ? 'dirty' : ''}>
                                      {t.tablePreset}
                                      <select
                                        value={effectivePresetId}
                                        onChange={(event) =>
                                          (() => {
                                            const nextPresetId = event.target.value || null;
                                            const nextPreset = nextPresetId ? presetsMap[nextPresetId] : undefined;
                                            const nextOrientation = nextPreset
                                              ? detectOrientation(nextPreset.width, nextPreset.height)
                                              : null;
                                            const nextAutoCrop =
                                              nextOrientation &&
                                              file.orientation &&
                                              nextOrientation !== file.orientation;
                                            handleEditChange(file.id, {
                                              selected_preset_id: nextPresetId,
                                              crop_enabled: nextAutoCrop ? true : cropEnabled,
                                              crop_aspect: nextPreset?.aspect ?? '',
                                            });
                                          })()
                                        }
                                      >
                                        {presetOptions.map((preset) => (
                                          <option key={preset.id} value={preset.id}>
                                            {preset.label}
                                          </option>
                                        ))}
                                      </select>
                                    </label>
                                    <div className={`format-group ${formatDirty ? 'dirty' : ''}`}>
                                      <span>{t.formatsToGenerate}</span>
                                      <div className="format-options">
                                        {['webp', 'jpg', 'png'].map((fmt) => (
                                          <label key={fmt} className="toggle">
                                            <input
                                              type="checkbox"
                                              checked={effectiveFormats.includes(fmt)}
                                              onChange={(event) => {
                                                const next = new Set(effectiveFormats);
                                                if (event.target.checked) {
                                                  next.add(fmt);
                                                } else {
                                                  next.delete(fmt);
                                                }
                                                const ordered = ['webp', 'jpg', 'png'].filter((item) =>
                                                  next.has(item),
                                                );
                                                if (!ordered.length) return;
                                                handleEditChange(file.id, {
                                                  output_formats: ordered,
                                                  output_format: ordered[0],
                                                });
                                              }}
                                            />
                                            {fmt}
                                          </label>
                                        ))}
                                      </div>
                                      <span className="muted">
                                        {t.primaryLabel}: {primaryFormat}
                                      </span>
                                    </div>
                                    {effectiveFormats.includes('webp') && (
                                      <label className={qualityDirty ? 'dirty' : ''}>
                                        {t.qualityWebp} ({webpQuality})
                                        <input
                                          type="range"
                                          min={1}
                                          max={100}
                                          value={webpQuality}
                                          onChange={(event) => {
                                            const value = Number(event.target.value);
                                            handleEditChange(file.id, { quality_webp: value });
                                          }}
                                        />
                                      </label>
                                    )}
                                    {effectiveFormats.includes('jpg') && (
                                      <label className={qualityDirty ? 'dirty' : ''}>
                                        {t.qualityJpg} ({jpgQuality})
                                        <input
                                          type="range"
                                          min={1}
                                          max={100}
                                          value={jpgQuality}
                                          onChange={(event) => {
                                            const value = Number(event.target.value);
                                            handleEditChange(file.id, { quality_jpg: value });
                                          }}
                                        />
                                      </label>
                                    )}
                                    <label className={`toggle ${metadataDirty ? 'dirty' : ''}`}>
                                      <input
                                        type="checkbox"
                                        checked={removeMetadata}
                                        onChange={(event) =>
                                          handleEditChange(file.id, { keep_metadata: !event.target.checked })
                                        }
                                      />
                                      {t.removeMetadata}
                                    </label>
                                    <label className={`toggle ${transparencyDirty ? 'dirty' : ''}`}>
                                      <input
                                        type="checkbox"
                                        checked={keepTransparency}
                                        onChange={(event) =>
                                          handleEditChange(file.id, { keep_transparency: event.target.checked })
                                        }
                                      />
                                      {t.keepTransparency}
                                    </label>
                                    <label className={`toggle ${baseGenerate2x !== generate2x ? 'dirty' : ''}`}>
                                      <input
                                        type="checkbox"
                                        checked={generate2x}
                                        onChange={(event) =>
                                          handleEditChange(file.id, {
                                            generate_2x: event.target.checked,
                                            generate_sharpened: event.target.checked ? false : generateSharpened,
                                          })
                                        }
                                      />
                                      {t.generate2x}
                                    </label>
                                    <label
                                      className={`toggle ${
                                        baseGenerateSharpened !== generateSharpened ? 'dirty' : ''
                                      }`}
                                    >
                                      <input
                                        type="checkbox"
                                        checked={generateSharpened}
                                        disabled={generate2x}
                                        onChange={(event) =>
                                          handleEditChange(file.id, {
                                            generate_sharpened: event.target.checked,
                                            generate_2x: event.target.checked ? false : generate2x,
                                          })
                                        }
                                      />
                                      {t.sharpened}
                                    </label>
                                    {sharpRecommended && (
                                      <span className="badge">{t.recommendedPreset}</span>
                                    )}
                                    <label className={nameDirty ? 'dirty' : ''}>
                                      {t.resultNameLabel}
                                      <input type="text" value={namePreview} readOnly />
                                    </label>
                                  </div>
                                  <div className={`crop-controls ${cropDirty ? 'dirty' : ''}`}>
                                    <button
                                      className="ghost"
                                      type="button"
                                      onClick={() => {
                                        handleEditChange(file.id, {
                                          crop_enabled: true,
                                          crop_aspect: effectivePreset?.aspect ?? '',
                                        });
                                        setCropFileId(file.id);
                                      }}
                                    >
                                      {t.crop}
                                    </button>
                                  </div>
                                  {shouldAutoCrop && (
                                    <span className="badge">{t.autoCrop}</span>
                                  )}
                                  {noUpscaleWarning && (
                                    <span className="muted">{t.noUpscale}</span>
                                  )}
                                  <button
                                    className="primary"
                                    type="button"
                                    disabled={!isDirty}
                                    onClick={async () => {
                                      try {
                                        // Guarda overrides y reprocesa el archivo para reflejar ajustes.
                                        const payload: JobFileUpdatePayload = {
                                          selected_preset_id: effectivePresetId || null,
                                          output_format: primaryFormat,
                                          output_formats: effectiveFormats,
                                          quality_webp: effectiveFormats.includes('webp') ? Number(webpQuality) : null,
                                          quality_jpg: effectiveFormats.includes('jpg') ? Number(jpgQuality) : null,
                                          keep_metadata: !removeMetadata,
                                          keep_transparency: keepTransparency,
                                          rename_pattern: renamePattern,
                                          normalize_lowercase: normalizeLowercase,
                                          normalize_remove_accents: normalizeRemoveAccents,
                                          normalize_replace_spaces: normalizeReplaceSpaces,
                                          normalize_collapse_dashes: normalizeCollapseDashes,
                                          crop_enabled: cropEnabled,
                                          crop_aspect: effectivePreset?.aspect ?? '',
                                          crop_x: edits.crop_x ?? file.crop_x ?? null,
                                          crop_y: edits.crop_y ?? file.crop_y ?? null,
                                          crop_w: edits.crop_w ?? file.crop_w ?? null,
                                          crop_h: edits.crop_h ?? file.crop_h ?? null,
                                          generate_2x: generate2x,
                                          generate_sharpened: generateSharpened,
                                        };
                                        await updateJobFile(file.id, payload);
                                        await reprocessFile(file.id);
                                        await loadJob();
                                        setFileEdits((current) => ({ ...current, [file.id]: {} }));
                                        setInfo(t.settingsApplied);
                                      } catch (err) {
                                        setError(resolveErrorMessage(err, t.errorApplySettings, locale));
                                      }
                                    }}
                                  >
                                    {t.applySettings}
                                  </button>
                                  {isDirty && (
                                    <span className="muted">{t.pendingChanges}</span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                        <details className="recommendation">
                          <summary className="label">{t.recommendation}</summary>
                          <div className="recommendation-grid">
                            <span>
                              {t.recommendationPreset}: {file.recommended_preset_label ?? '-'}
                            </span>
                            <span>
                              {t.recommendationFormats}:{' '}
                              {file.recommended_formats && file.recommended_formats.length > 0
                                ? file.recommended_formats.filter((fmt) => fmt !== 'avif').join(', ')
                                : '-'}
                            </span>
                            <span>
                              {t.recommendationQuality}:{' '}
                              {file.recommended_quality
                                ? Object.entries(file.recommended_quality)
                                    .map(([key, value]) => `${key}=${value}`)
                                    .join(', ')
                                : '-'}
                            </span>
                            <span>
                              {t.recommendationNote}: {file.recommended_notes ?? '-'}
                            </span>
                          </div>
                          {file.recommended_crop_mode === 'cover' && (
                            <span className="badge">{t.recommendationCrop}</span>
                          )}
                          {file.recommended_crop_reason && (
                            <span className="muted">{file.recommended_crop_reason}</span>
                          )}
                        </details>
                      </>
                    );
                  })()}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}


      {cropFile && (
        <CropModal
          open={Boolean(cropFile)}
          imageUrl={cropFile.original_url ?? ''}
          aspect={parseAspect(
            presetsMap[
              fileEdits[cropFile.id]?.selected_preset_id ??
                cropFile.selected_preset_id ??
                job?.preset ??
                cropFile.recommended_preset_id ??
                ''
            ]?.aspect ?? '1:1',
          )}
          initialCrop={(() => {
            const edits = fileEdits[cropFile.id] ?? {};
            const crop_x = edits.crop_x ?? cropFile.crop_x;
            const crop_y = edits.crop_y ?? cropFile.crop_y;
            const crop_w = edits.crop_w ?? cropFile.crop_w;
            const crop_h = edits.crop_h ?? cropFile.crop_h;
            if (crop_x != null && crop_y != null && crop_w != null && crop_h != null) {
              return { crop_x, crop_y, crop_w, crop_h };
            }
            return null;
          })()}
          onCancel={() => setCropFileId(null)}
          onSave={(crop) => {
            if (!cropFile) return;
            const presetId =
              fileEdits[cropFile.id]?.selected_preset_id ??
              cropFile.selected_preset_id ??
              job?.preset ??
              cropFile.recommended_preset_id ??
              '';
            handleEditChange(cropFile.id, {
              crop_enabled: true,
              crop_aspect: presetsMap[presetId]?.aspect ?? '',
              ...crop,
            });
            setCropFileId(null);
            setInfo(t.cropReady);
          }}
        />
      )}
    </section>
  );
}

function buildSnippet(
  file: JobFileReport,
  basePath: string,
  presetsMap: Record<string, PresetItem>,
  job: JobDetail,
) {
  // Genera un snippet <img>/<picture> según formatos y variantes disponibles.
  const includeSize = localStorage.getItem('snippetIncludeSize') !== 'false';
  const loadingAttr = localStorage.getItem('snippetLazy') === 'false' ? '' : 'lazy';
  const decodingAttr = localStorage.getItem('snippetDecoding') || 'async';
  const presetId = file.selected_preset_id ?? job.preset ?? file.recommended_preset_id ?? '';
  const preset = presetId ? presetsMap[presetId] : undefined;
  const width = file.output_width ?? preset?.width ?? file.original_width ?? 0;
  const height = file.output_height ?? preset?.height ?? file.original_height ?? 0;
  const safeBase = basePath?.trim() || '/img/';
  const prefix = safeBase.endsWith('/') ? safeBase : `${safeBase}/`;
  const variants = file.output_variants ?? [];
  const outputName = file.output_name ?? variants[0]?.name ?? '';
  const formats = Array.from(new Set(variants.map((variant) => variant.format)));
  const has2x = variants.some((variant) => variant.scale === '2x');
  const sizeAttrs = includeSize ? ` width="${width}" height="${height}"` : '';
  const loadingPart = loadingAttr ? ` loading="${loadingAttr}"` : '';
  const decodingPart = decodingAttr ? ` decoding="${decodingAttr}"` : '';

  if (variants.length > 0 && (formats.length > 1 || has2x)) {
    const formatOrder = ['webp', 'jpg', 'png'];
    const sources = formatOrder
      .filter((fmt) => formats.includes(fmt))
      .map((fmt) => {
        const items = variants.filter((variant) => variant.format === fmt);
        const srcset = items
          .map((variant) => `${prefix}${variant.name} ${variant.scale || '1x'}`)
          .join(', ');
        const type = fmt === 'jpg' ? 'image/jpeg' : `image/${fmt}`;
        return `  <source type="${type}" srcset="${srcset}">`;
      })
      .join('\n');
    return `<picture>\n${sources}\n  <img src="${prefix}${outputName}"${sizeAttrs}${loadingPart}${decodingPart} alt="">\n</picture>`;
  }

  return `<img src="${prefix}${outputName}"${sizeAttrs}${loadingPart}${decodingPart} alt="">`;
}

function parseAspect(aspect: string | undefined): number {
  // Convierte "W:H" en ratio numérico para el recorte.
  if (!aspect) return 1;
  const parts = aspect.split(':');
  if (parts.length !== 2) return 1;
  const w = Number(parts[0]);
  const h = Number(parts[1]);
  if (!Number.isFinite(w) || !Number.isFinite(h) || h === 0) return 1;
  return w / h;
}

function buildAspectRatio(width?: number | null, height?: number | null): number {
  // Fallback de ratio para tarjetas de vista previa.
  if (!width || !height) return 16 / 9;
  return width / height;
}

function buildNamePreview(
  originalName: string,
  presetId: string,
  format: string,
  pattern: string,
  lowercase: boolean,
  removeAccents: boolean,
  replaceSpaces: string,
  collapseDashes: boolean,
) {
  // Simula el nombre final sin tocar archivos reales.
  const base = originalName.replace(/\.[^/.]+$/, '');
  const normalized = normalizeName(base, lowercase, removeAccents, replaceSpaces, collapseDashes);
  return pattern
    .replace('{preset}', presetId ?? '')
    .replace('{ext}', format ?? 'webp')
    .replace('{name-normalized}', normalized)
    .replace('{name}', base);
}

function normalizeName(
  value: string,
  lowercase: boolean,
  removeAccents: boolean,
  replaceSpaces: string,
  collapseDashes: boolean,
) {
  // Normaliza el nombre siguiendo reglas de preset y overrides.
  let text = value;
  if (removeAccents) {
    text = text.normalize('NFD').replace(/\p{Diacritic}/gu, '');
  }
  if (lowercase) {
    text = text.toLowerCase();
  }
  if (replaceSpaces !== undefined) {
    text = text.replace(/\s+/g, replaceSpaces);
  }
  if (collapseDashes) {
    while (text.includes('--')) {
      text = text.replace(/--/g, '-');
    }
  }
  return text.trim();
}

function detectOrientation(width?: number, height?: number) {
  // Clasifica la orientación con reglas simples.
  if (!width || !height) return null;
  if (width > height) return 'HORIZONTAL';
  if (height > width) return 'VERTICAL';
  return 'CUADRADA';
}

function arraysEqual(left: string[], right: string[]) {
  // Comparación simple para detectar cambios en formatos seleccionados.
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}

function buildOutputsSummary(variants: JobFileReport['output_variants']) {
  // Resumen corto de las salidas generadas.
  if (!variants || variants.length === 0) return '-';
  return variants
    .map((variant) => `${variant.format} ${variant.scale}`)
    .join(', ');
}
