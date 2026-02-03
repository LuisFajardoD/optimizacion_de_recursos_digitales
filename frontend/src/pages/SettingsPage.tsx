import { useEffect, useMemo, useRef, useState } from 'react';

import type { AppSettings, PresetItem } from '../services/api';
import {
  createCustomPreset,
  deleteCustomPreset,
  duplicateCustomPreset,
  fetchPresets,
  getSettings,
  updateCustomPreset,
  updateSettings,
} from '../services/api';
import { resolveErrorMessage, useI18n } from '../services/i18n';

const CATEGORIES = ['web', 'redes', 'ecommerce'] as const;
const TYPE_HINTS = ['photo', 'ui'] as const;
const DENSITIES = ['standard', 'suggestHigherDpi'] as const;
const DEFAULT_APP_SETTINGS: AppSettings = {
  concurrency: 4,
  default_remove_metadata: true,
  default_keep_transparency: true,
  show_debug_details: false,
};
const DEFAULT_THEME = 'dark';
const DEFAULT_LOCALE: 'es' | 'es-mx' | 'en' = 'es';
const DEFAULT_SNIPPET_LAZY = true;
const DEFAULT_SNIPPET_DECODING = 'async';
const DEFAULT_SNIPPET_INCLUDE_SIZE = true;

function applyTheme(theme: string) {
  const root = document.documentElement;
  if (theme === 'light') {
    root.classList.add('theme-light');
    root.classList.remove('theme-dark');
  } else {
    root.classList.add('theme-dark');
    root.classList.remove('theme-light');
  }
}

function buildSettingsSnapshot(
  settings: AppSettings | null | undefined,
  theme: string,
  locale: 'es' | 'es-mx' | 'en',
  snippetLazy: boolean,
  snippetDecoding: string,
  snippetIncludeSize: boolean,
) {
  if (!settings) return null;
  return JSON.stringify({
    settings: {
      concurrency: Number(settings.concurrency),
      default_remove_metadata: Boolean(settings.default_remove_metadata),
      default_keep_transparency: Boolean(settings.default_keep_transparency),
      show_debug_details: Boolean(settings.show_debug_details),
    },
    theme,
    locale,
    snippetLazy: Boolean(snippetLazy),
    snippetDecoding,
    snippetIncludeSize: Boolean(snippetIncludeSize),
  });
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [pendingSettings, setPendingSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
  const { locale, setLocale, t, presetLabel } = useI18n();
  const [snippetLazy, setSnippetLazy] = useState(() => {
    const value = localStorage.getItem('snippetLazy');
    return value ? value === 'true' : true;
  });
  const [snippetDecoding, setSnippetDecoding] = useState(
    () => localStorage.getItem('snippetDecoding') || 'async',
  );
  const [snippetIncludeSize, setSnippetIncludeSize] = useState(() => {
    const value = localStorage.getItem('snippetIncludeSize');
    return value ? value === 'true' : true;
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const savedRef = useRef<{
    settings: AppSettings;
    theme: string;
    locale: 'es' | 'es-mx' | 'en';
    snippetLazy: boolean;
    snippetDecoding: string;
    snippetIncludeSize: boolean;
  } | null>(null);
  const [form, setForm] = useState({
    id: '',
    label: '',
    category: 'web',
    width: '',
    height: '',
    aspect: '1:1',
    typeHint: 'photo',
    density: 'standard',
    recommendedFormat: '',
  });

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getSettings();
        setSettings(data);
        setPendingSettings(data);
        savedRef.current = {
          settings: data,
          theme,
          locale,
          snippetLazy,
          snippetDecoding,
          snippetIncludeSize,
        };
        setError('');
      } catch (err) {
        setError(resolveErrorMessage(err, t.errorLoadSettings, locale));
      }
    };
    void load();
  }, [t.errorLoadSettings]);

  const loadPresets = async () => {
    try {
      const data = await fetchPresets();
      setPresets(data.presets ?? []);
    } catch {
      setPresets([]);
    }
  };

  useEffect(() => {
    void loadPresets();
  }, []);

  const customPresets = useMemo(
    () => presets.filter((preset) => preset.source === 'custom'),
    [presets],
  );

  const handleSettingsPatch = async (payload: Partial<AppSettings>) => {
    if (!settings) return;
    try {
      const updated = await updateSettings(payload);
      setSettings(updated);
      setPendingSettings(updated);
      savedRef.current = {
        settings: updated,
        theme,
        locale,
        snippetLazy,
        snippetDecoding,
        snippetIncludeSize,
      };
      localStorage.setItem('theme', theme);
      localStorage.setItem('snippetLazy', String(snippetLazy));
      localStorage.setItem('snippetDecoding', snippetDecoding);
      localStorage.setItem('snippetIncludeSize', String(snippetIncludeSize));
      setInfo(t.settingsSaved);
      setTimeout(() => setInfo(''), 2000);
    } catch (err) {
      setError(resolveErrorMessage(err, t.errorSaveSettings, locale));
    }
  };

  const resetSettings = async () => {
    try {
      const updated = await updateSettings(DEFAULT_APP_SETTINGS);
      setSettings(updated);
      setPendingSettings(updated);
      setTheme(DEFAULT_THEME);
      setLocale(DEFAULT_LOCALE);
      setSnippetLazy(DEFAULT_SNIPPET_LAZY);
      setSnippetDecoding(DEFAULT_SNIPPET_DECODING);
      setSnippetIncludeSize(DEFAULT_SNIPPET_INCLUDE_SIZE);
      localStorage.setItem('theme', DEFAULT_THEME);
      localStorage.setItem('snippetLazy', String(DEFAULT_SNIPPET_LAZY));
      localStorage.setItem('snippetDecoding', DEFAULT_SNIPPET_DECODING);
      localStorage.setItem('snippetIncludeSize', String(DEFAULT_SNIPPET_INCLUDE_SIZE));
      savedRef.current = {
        settings: updated,
        theme: DEFAULT_THEME,
        locale: DEFAULT_LOCALE,
        snippetLazy: DEFAULT_SNIPPET_LAZY,
        snippetDecoding: DEFAULT_SNIPPET_DECODING,
        snippetIncludeSize: DEFAULT_SNIPPET_INCLUDE_SIZE,
      };
      setInfo(t.settingsReset);
      setTimeout(() => setInfo(''), 2000);
    } catch (err) {
      setError(resolveErrorMessage(err, t.errorSaveSettings, locale));
    }
  };

  const cancelChanges = () => {
    const saved = savedRef.current;
    if (!saved) return;
    setPendingSettings(saved.settings);
    setTheme(saved.theme);
    setLocale(saved.locale);
    setSnippetLazy(saved.snippetLazy);
    setSnippetDecoding(saved.snippetDecoding);
    setSnippetIncludeSize(saved.snippetIncludeSize);
    localStorage.setItem('theme', saved.theme);
    localStorage.setItem('snippetLazy', String(saved.snippetLazy));
    localStorage.setItem('snippetDecoding', saved.snippetDecoding);
    localStorage.setItem('snippetIncludeSize', String(saved.snippetIncludeSize));
    setInfo(t.settingsCanceled);
    setTimeout(() => setInfo(''), 2000);
  };

  const currentSnapshot = buildSettingsSnapshot(
    pendingSettings ?? settings,
    theme,
    locale,
    snippetLazy,
    snippetDecoding,
    snippetIncludeSize,
  );
  const savedSnapshot = savedRef.current
    ? buildSettingsSnapshot(
        savedRef.current.settings,
        savedRef.current.theme,
        savedRef.current.locale,
        savedRef.current.snippetLazy,
        savedRef.current.snippetDecoding,
        savedRef.current.snippetIncludeSize,
      )
    : null;
  const defaultSnapshot = buildSettingsSnapshot(
    DEFAULT_APP_SETTINGS,
    DEFAULT_THEME,
    DEFAULT_LOCALE,
    DEFAULT_SNIPPET_LAZY,
    DEFAULT_SNIPPET_DECODING,
    DEFAULT_SNIPPET_INCLUDE_SIZE,
  );
  const isSettingsDirty = Boolean(savedSnapshot && currentSnapshot && savedSnapshot !== currentSnapshot);
  const isResetAvailable = Boolean(savedSnapshot && defaultSnapshot && savedSnapshot !== defaultSnapshot);

  const resetForm = () => {
    setEditingId(null);
    setForm({
      id: '',
      label: '',
      category: 'web',
      width: '',
      height: '',
      aspect: '1:1',
      typeHint: 'photo',
      density: 'standard',
      recommendedFormat: '',
    });
  };

  const submitPreset = async () => {
    setError('');
    try {
      if (editingId) {
        await updateCustomPreset(editingId, {
          label: form.label,
          category: form.category,
          width: Number(form.width),
          height: Number(form.height),
          aspect: form.aspect,
          typeHint: form.typeHint,
          density: form.density,
          recommendedFormat: form.recommendedFormat || undefined,
        });
      } else {
        await createCustomPreset({
          id: form.id,
          label: form.label,
          category: form.category,
          width: Number(form.width),
          height: Number(form.height),
          aspect: form.aspect,
          typeHint: form.typeHint,
          density: form.density,
          recommendedFormat: form.recommendedFormat || undefined,
        });
      }
      await loadPresets();
      resetForm();
      setInfo(t.presetSaved);
      setTimeout(() => setInfo(''), 2000);
    } catch (err) {
      setError(resolveErrorMessage(err, t.errorSavePreset, locale));
    }
  };

  return (
    <section className="page">
      <header className="page-header">
        <div>
          <h1>{t.settingsTitle}</h1>
          <p>{t.settingsSubtitle}</p>
        </div>
        <div className="settings-actions">
          <button
            className="primary"
            type="button"
            disabled={!isSettingsDirty}
            onClick={() => {
              if (!pendingSettings) return;
              void handleSettingsPatch(pendingSettings);
            }}
          >
            {t.saveSettings}
          </button>
          <button className="ghost" type="button" disabled={!isSettingsDirty} onClick={cancelChanges}>
            {t.cancelSettings}
          </button>
          <button className="ghost" type="button" disabled={!isResetAvailable} onClick={resetSettings}>
            {t.resetSettings}
          </button>
        </div>
      </header>

      <div className="panel">
        <h2>{t.preferences}</h2>
        <div className="settings-grid">
          <label>
            {t.theme}
            <select value={theme} onChange={(event) => setTheme(event.target.value)}>
              <option value="dark">{t.themeDark}</option>
              <option value="light">{t.themeLight}</option>
            </select>
          </label>
          <label>
            {t.language}
            <select value={locale} onChange={(event) => setLocale(event.target.value as 'es' | 'es-mx' | 'en')}>
              <option value="es">{t.languageEs}</option>
              <option value="es-mx">{t.languageEsMx}</option>
              <option value="en">{t.languageEn}</option>
            </select>
          </label>
          <label>
            {t.settingsConcurrencyValue.replace(
              '{value}',
              String(pendingSettings?.concurrency ?? settings?.concurrency ?? 3),
            )}
            <input
              type="range"
              min={1}
              max={10}
              value={pendingSettings?.concurrency ?? settings?.concurrency ?? 3}
              onChange={(event) =>
                setPendingSettings((current) =>
                  current
                    ? { ...current, concurrency: Number(event.target.value) }
                    : current
                )
              }
            />
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={pendingSettings?.default_remove_metadata ?? settings?.default_remove_metadata ?? true}
              onChange={(event) =>
                setPendingSettings((current) =>
                  current
                    ? { ...current, default_remove_metadata: event.target.checked }
                    : current
                )
              }
            />
            {t.defaultRemoveMetadata}
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={pendingSettings?.default_keep_transparency ?? settings?.default_keep_transparency ?? true}
              onChange={(event) =>
                setPendingSettings((current) =>
                  current
                    ? { ...current, default_keep_transparency: event.target.checked }
                    : current
                )
              }
            />
            {t.defaultKeepTransparency}
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={pendingSettings?.show_debug_details ?? settings?.show_debug_details ?? false}
              onChange={(event) =>
                setPendingSettings((current) =>
                  current
                    ? { ...current, show_debug_details: event.target.checked }
                    : current
                )
              }
            />
            {t.showDebugDetails}
          </label>
        </div>
      </div>

      <div className="panel">
        <h2>{t.snippetTitle}</h2>
        <div className="settings-grid">
          <label className="toggle">
            <input
              type="checkbox"
              checked={snippetLazy}
              onChange={(event) => setSnippetLazy(event.target.checked)}
            />
            {t.loadingLazy}
          </label>
          <label>
            {t.decodingLabel}
            <select
              value={snippetDecoding}
              onChange={(event) => setSnippetDecoding(event.target.value)}
            >
              <option value="async">async</option>
              <option value="auto">auto</option>
              <option value="sync">sync</option>
            </select>
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={snippetIncludeSize}
              onChange={(event) => setSnippetIncludeSize(event.target.checked)}
            />
            {t.includeSize}
          </label>
        </div>
      </div>

      <div className="panel">
        <h2>{t.presetsCustom}</h2>
        <div className="settings-grid">
          {!editingId && (
            <label>
              {t.presetId}
              <input
                type="text"
                value={form.id}
                onChange={(event) => setForm((current) => ({ ...current, id: event.target.value }))}
              />
            </label>
          )}
          <label>
            {t.presetLabel}
            <input
              type="text"
              value={form.label}
              onChange={(event) => setForm((current) => ({ ...current, label: event.target.value }))}
            />
          </label>
          <label>
            {t.presetCategory}
            <select
              value={form.category}
              onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}
            >
              {CATEGORIES.map((item) => (
                <option key={item} value={item}>
                  {presetLabel(item)}
                </option>
              ))}
            </select>
          </label>
          <div className="inline-fields">
            <label>
              {t.presetWidth}
              <input
                type="number"
                min={1}
                value={form.width}
                onChange={(event) => setForm((current) => ({ ...current, width: event.target.value }))}
              />
            </label>
            <label>
              {t.presetHeight}
              <input
                type="number"
                min={1}
                value={form.height}
                onChange={(event) => setForm((current) => ({ ...current, height: event.target.value }))}
              />
            </label>
          </div>
          <label>
            {t.presetAspect}
            <input
              type="text"
              value={form.aspect}
              onChange={(event) => setForm((current) => ({ ...current, aspect: event.target.value }))}
            />
          </label>
          <label>
            {t.presetTypeHint}
            <select
              value={form.typeHint}
              onChange={(event) => setForm((current) => ({ ...current, typeHint: event.target.value }))}
            >
            {TYPE_HINTS.map((item) => (
              <option key={item} value={item}>
                {item === 'photo' ? t.photoLabel.toLowerCase() : 'ui'}
              </option>
            ))}
          </select>
        </label>
          <label>
            {t.presetDensity}
            <select
              value={form.density}
              onChange={(event) => setForm((current) => ({ ...current, density: event.target.value }))}
            >
            {DENSITIES.map((item) => (
              <option key={item} value={item}>
                {item === 'standard' ? t.standardLabel : t.higherDpiLabel}
              </option>
            ))}
          </select>
        </label>
          <label>
            {t.presetRecommendedFormat}
            <select
              value={form.recommendedFormat}
              onChange={(event) =>
                setForm((current) => ({ ...current, recommendedFormat: event.target.value }))
              }
            >
              <option value="">-</option>
              <option value="webp">WebP</option>
              <option value="jpg">JPG</option>
              <option value="png">PNG</option>
            </select>
          </label>
        </div>
        <div className="actions">
          <button className="primary" type="button" onClick={submitPreset}>
            {editingId ? t.saveChanges : t.createPreset}
          </button>
          {editingId && (
            <button className="ghost" type="button" onClick={resetForm}>
              {t.cancelEdit}
            </button>
          )}
        </div>

        <div className="preset-list">
          {customPresets.length === 0 && <p className="muted">{t.noCustomPresets}</p>}
          {customPresets.map((preset) => (
            <div className="preset-row" key={preset.id}>
              <div>
                <strong>{preset.label}</strong>
                <span className="muted">
                  {preset.id} · {preset.width}×{preset.height} · {presetLabel(preset.category)}
                </span>
              </div>
              <div className="preset-actions">
                <button
                  className="ghost"
                  type="button"
                  onClick={() => {
                    setEditingId(preset.id);
                    setForm({
                      id: preset.id,
                      label: preset.label,
                      category: preset.category,
                      width: String(preset.width),
                      height: String(preset.height),
                      aspect: preset.aspect,
                      typeHint: preset.typeHint,
                      density: preset.density ?? 'standard',
                      recommendedFormat: preset.recommendedFormat ?? '',
                    });
                  }}
                >
                  {t.edit}
                </button>
                <button
                  className="ghost"
                  type="button"
                  onClick={async () => {
                    try {
                      await duplicateCustomPreset(preset.id);
                      await loadPresets();
                    } catch (err) {
                      setError(resolveErrorMessage(err, t.errorDuplicatePreset, locale));
                    }
                  }}
                >
                  {t.duplicate}
                </button>
                <button
                  className="ghost"
                  type="button"
                  onClick={async () => {
                    if (!confirm(t.confirmDelete)) return;
                    try {
                      await deleteCustomPreset(preset.id);
                      await loadPresets();
                    } catch (err) {
                      setError(resolveErrorMessage(err, t.errorDeletePreset, locale));
                    }
                  }}
                >
                  {t.delete}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="toast toast-error">
          {error}
        </div>
      )}
      {info && (
        <div className="toast">
          {info}
        </div>
      )}
    </section>
  );
}
