import {
	App,
	Notice,
	Plugin,
	PluginSettingTab,
	Setting,
	TFile,
	normalizePath,
} from "obsidian";
import { createHash, randomUUID } from "node:crypto";

interface TextifAIBridgeSettings {
	exportPath: string;
	autoExportOnStartup: boolean;
	autoExportOnResolved: boolean;
	autoExportOnVaultChange: boolean;
	debounceMs: number;
	includeFullText: boolean;
	installationId: string;
	exportSequence: number;
}

const SNAPSHOT_SCHEMA_VERSION = "2.0";

const DEFAULT_SETTINGS: TextifAIBridgeSettings = {
	exportPath: ".textifai/obsidian-bridge-snapshot.json",
	autoExportOnStartup: true,
	autoExportOnResolved: true,
	autoExportOnVaultChange: true,
	debounceMs: 800,
	includeFullText: true,
	installationId: "",
	exportSequence: 0,
};

export default class TextifAIBridgePlugin extends Plugin {
	settings: TextifAIBridgeSettings = DEFAULT_SETTINGS;
	private exportTimer: ReturnType<typeof setTimeout> | null = null;
	private exportInProgress = false;
	private rerunRequested = false;
	private dirtyReasons = new Set<string>();

	async onload(): Promise<void> {
		await this.loadSettings();
		this.addCommand({
			id: "export-textifai-context-snapshot",
			name: "Export TextifAI context snapshot",
			callback: async () => {
				this.markDirty("manual_command");
				await this.flushExportQueue();
				new Notice("TextifAI snapshot exported");
			},
		});
		this.addSettingTab(new TextifAIBridgeSettingTab(this.app, this));

		this.app.workspace.onLayoutReady(() => {
			if (this.settings.autoExportOnStartup) {
				this.scheduleExport("startup");
			}
		});

		this.registerEvent(
			this.app.metadataCache.on("resolved", () => {
				if (this.settings.autoExportOnResolved) {
					this.scheduleExport("metadata_resolved");
				}
			}),
		);

		this.registerEvent(
			this.app.metadataCache.on("changed", (file) => {
				if (this.settings.autoExportOnVaultChange && file instanceof TFile && file.extension === "md") {
					this.scheduleExport("metadata_changed");
				}
			}),
		);

		this.registerEvent(
			this.app.vault.on("create", (file) => {
				if (this.settings.autoExportOnVaultChange && file instanceof TFile && file.extension === "md") {
					this.scheduleExport("vault_create");
				}
			}),
		);

		this.registerEvent(
			this.app.vault.on("rename", (file) => {
				if (this.settings.autoExportOnVaultChange && file instanceof TFile && file.extension === "md") {
					this.scheduleExport("vault_rename");
				}
			}),
		);

		this.registerEvent(
			this.app.vault.on("delete", (file) => {
				if (this.settings.autoExportOnVaultChange && file instanceof TFile && file.extension === "md") {
					this.scheduleExport("vault_delete");
				}
			}),
		);
	}

	onunload(): void {
		if (this.exportTimer) {
			clearTimeout(this.exportTimer);
			this.exportTimer = null;
		}
	}

	private scheduleExport(reason: string): void {
		this.markDirty(reason);
		if (this.exportTimer) {
			clearTimeout(this.exportTimer);
		}
		this.exportTimer = setTimeout(() => {
			void this.flushExportQueue();
		}, this.settings.debounceMs);
	}

	private markDirty(reason: string): void {
		this.dirtyReasons.add(reason);
		if (this.exportInProgress) {
			this.rerunRequested = true;
		}
	}

	private async flushExportQueue(): Promise<void> {
		if (this.exportInProgress) {
			this.rerunRequested = true;
			return;
		}
		this.exportInProgress = true;
		try {
			do {
				this.rerunRequested = false;
				const reasons = Array.from(this.dirtyReasons);
				this.dirtyReasons.clear();
				await this.exportSnapshot(reasons);
			} while (this.rerunRequested || this.dirtyReasons.size > 0);
		} finally {
			this.exportInProgress = false;
		}
	}

	private async exportSnapshot(reasons: string[]): Promise<void> {
		const files = this.app.vault.getMarkdownFiles();
		const notes: Array<{
			note_id: string;
			title: string;
			path: string;
			vault_relative_path: string;
			canonical_path: string;
			artifact_type: string;
			file_mtime: number;
			file_ctime: number;
			file_size: number;
			cache_complete: boolean;
			frontmatter: Record<string, unknown>;
			aliases: string[];
			project_confirmed_aliases: string[];
			outgoing_links: string[];
			incoming_links: string[];
			raw_text: string;
			body_text: string;
			tags: string[];
			headings: Array<Record<string, unknown>>;
			sections: Array<Record<string, unknown>>;
			wikilinks: Array<Record<string, unknown>>;
			embeds: Array<Record<string, unknown>>;
			frontmatter_links: Array<Record<string, unknown>>;
			resolved_links: Record<string, number>;
			unresolved_links: Record<string, number>;
			source_kind: string;
		}> = [];
		const incomingByTarget: Record<string, Set<string>> = {};
		const warnings: string[] = [];
		const errors: string[] = [];

		for (const file of files) {
			try {
				const cache = this.app.metadataCache.getFileCache(file);
				const body = this.settings.includeFullText ? await this.app.vault.cachedRead(file) : "";
				const resolved = this.app.metadataCache.resolvedLinks[file.path] ?? {};
				const unresolved = this.app.metadataCache.unresolvedLinks[file.path] ?? {};
				const links = (cache?.links ?? []).map((link) => buildLinkRecord(link.link, file.path, false, this.app));
				const embeds = (cache?.embeds ?? []).map((embed) => buildLinkRecord(embed.link, file.path, true, this.app));
				const frontmatterLinks = (cache?.frontmatterLinks ?? []).map((link) => buildLinkRecord(link.link, file.path, false, this.app));

				for (const targetPath of Object.keys(resolved)) {
					const normalizedTarget = normalizeVaultPath(targetPath.replace(/\.md$/i, ""));
					incomingByTarget[normalizedTarget] ??= new Set<string>();
					incomingByTarget[normalizedTarget].add(normalizeVaultPath(file.path.replace(/\.md$/i, "")));
				}

				notes.push({
					note_id: noteIdFromPath(file.path),
					title: file.basename,
					path: file.path,
					vault_relative_path: file.path,
					canonical_path: normalizeVaultPath(file.path),
					artifact_type: inferArtifactType(file.path),
					file_mtime: file.stat.mtime,
					file_ctime: file.stat.ctime,
					file_size: file.stat.size,
					cache_complete: cache != null,
					frontmatter: cache?.frontmatter ?? {},
					aliases: normalizeAliases(cache?.frontmatter?.aliases),
					project_confirmed_aliases: normalizeAliases(cache?.frontmatter?.project_confirmed_aliases),
					outgoing_links: Object.keys(resolved).map(noteIdFromPath),
					incoming_links: [],
					raw_text: body,
					body_text: body,
					tags: normalizeTags((cache?.tags ?? []).map((tag) => tag.tag)),
					headings: (cache?.headings ?? []).map((heading) => ({
						heading: heading.heading,
						level: heading.level,
					})),
					sections: (cache?.sections ?? []).map((section) => ({
						type: section.type,
						start_line: section.position.start.line,
						end_line: section.position.end.line,
					})),
					wikilinks: links,
					embeds,
					frontmatter_links: frontmatterLinks,
					resolved_links: Object.fromEntries(
						Object.entries(resolved).map(([path, count]) => [noteIdFromPath(path), count]),
					),
					unresolved_links: unresolved,
					source_kind: "obsidian_bridge_snapshot",
				});
			} catch (error) {
				errors.push(`${file.path}: ${String(error)}`);
			}
		}

		for (const note of notes) {
			const incoming = incomingByTarget[normalizeVaultPath(note.vault_relative_path.replace(/\.md$/i, ""))];
			note.incoming_links = incoming ? Array.from(incoming).map(noteIdFromPath).sort() : [];
		}

		const vaultRootHint = getVaultRootHint(this.app);
		const generatedAt = new Date();
		const nextSequence = this.settings.exportSequence + 1;
		const payload = {
			schema_version: SNAPSHOT_SCHEMA_VERSION,
			source: "obsidian_textifai_bridge",
			generated_at: generatedAt.toISOString(),
			generated_unix_ms: generatedAt.getTime(),
			vault_name: this.app.vault.getName(),
			vault_id: buildVaultId(this.app, vaultRootHint),
			installation_id: this.settings.installationId,
			vault_root_hint: vaultRootHint,
			plugin_version: this.manifest.version,
			obsidian_app_version: (this.app as App & { version?: string }).version ?? null,
			export_reason: reasons.join(",") || "manual_command",
			export_sequence: nextSequence,
			export_complete: errors.length === 0,
			note_count: notes.length,
			bridge_capabilities: {
				metadata_cache: true,
				resolved_links: true,
				unresolved_links: true,
				headings: true,
				sections: true,
				tags: true,
				wikilinks: true,
				embeds: true,
				frontmatter_links: true,
				atomic_snapshot_write: true,
			},
			warnings,
			errors,
			notes,
		};

		await writeSnapshotAtomically(this.app, normalizePath(this.settings.exportPath), JSON.stringify(payload, null, 2));
		this.settings.exportSequence = nextSequence;
		await this.saveSettings();
	}

	private async loadSettings(): Promise<void> {
		const loaded = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
		if (!loaded.installationId) {
			loaded.installationId = randomUUID();
		}
		this.settings = loaded;
		await this.saveSettings();
	}

	async saveSettings(): Promise<void> {
		await this.saveData(this.settings);
	}
}

class TextifAIBridgeSettingTab extends PluginSettingTab {
	plugin: TextifAIBridgePlugin;

	constructor(app: App, plugin: TextifAIBridgePlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		new Setting(containerEl)
			.setName("Export path")
			.setDesc("Vault-relative JSON path for the TextifAI snapshot.")
			.addText((text) =>
				text
					.setPlaceholder(".textifai/obsidian-bridge-snapshot.json")
					.setValue(this.plugin.settings.exportPath)
					.onChange(async (value) => {
						this.plugin.settings.exportPath = value.trim() || DEFAULT_SETTINGS.exportPath;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName("Auto-export on startup")
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.autoExportOnStartup).onChange(async (value) => {
					this.plugin.settings.autoExportOnStartup = value;
					await this.plugin.saveSettings();
				}),
			);

		new Setting(containerEl)
			.setName("Auto-export after metadata resolution")
			.setDesc("Uses metadataCache.on('resolved') to export a fresh snapshot after Obsidian finishes resolving links.")
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.autoExportOnResolved).onChange(async (value) => {
					this.plugin.settings.autoExportOnResolved = value;
					await this.plugin.saveSettings();
				}),
			);

		new Setting(containerEl)
			.setName("Auto-export on vault changes")
			.setDesc("Uses metadataCache changed plus vault create/rename/delete events. Exports are debounced and serialized.")
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.autoExportOnVaultChange).onChange(async (value) => {
					this.plugin.settings.autoExportOnVaultChange = value;
					await this.plugin.saveSettings();
				}),
			);

		new Setting(containerEl)
			.setName("Include full text")
			.setDesc("Exports cached markdown body for TextifAI context retrieval.")
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.includeFullText).onChange(async (value) => {
					this.plugin.settings.includeFullText = value;
					await this.plugin.saveSettings();
				}),
			);
	}
}

async function writeSnapshotAtomically(app: App, outputPath: string, payload: string): Promise<void> {
	const adapter = app.vault.adapter as {
		mkdir?: (path: string) => Promise<void>;
		write: (path: string, data: string) => Promise<void>;
		rename?: (oldPath: string, newPath: string) => Promise<void>;
		remove?: (path: string) => Promise<void>;
		exists?: (path: string) => Promise<boolean>;
	};
	const dir = outputPath.includes("/") ? outputPath.slice(0, outputPath.lastIndexOf("/")) : "";
	if (dir && adapter.mkdir) {
		try {
			await adapter.mkdir(dir);
		} catch {}
	}
	const tempPath = `${outputPath}.tmp`;
	await adapter.write(tempPath, payload);
	if (adapter.exists && adapter.remove) {
		try {
			if (await adapter.exists(outputPath)) {
				await adapter.remove(outputPath);
			}
		} catch {}
	}
	if (adapter.rename) {
		await adapter.rename(tempPath, outputPath);
		return;
	}
	await adapter.write(outputPath, payload);
	if (adapter.remove) {
		try {
			await adapter.remove(tempPath);
		} catch {}
	}
}

function buildLinkRecord(linkPath: string, sourcePath: string, isEmbed: boolean, app: App) {
	const resolved = app.metadataCache.getFirstLinkpathDest(linkPath, sourcePath);
	return {
		link_text: linkPath,
		normalized_link_text: normalizeVaultPath(linkPath),
		is_embed: isEmbed,
		resolved_path: resolved?.path ?? null,
		resolved_note_id: resolved ? noteIdFromPath(resolved.path) : null,
	};
}

function inferArtifactType(path: string): string {
	const normalized = normalizeVaultPath(path);
	if (normalized.startsWith("03_characters/profiles/")) return "character";
	if (normalized.startsWith("02_world/lore/")) return "lore";
	if (normalized.startsWith("04_outline/scenes/")) return "scene";
	if (normalized.startsWith("05_draft/chapters/")) return "chapter";
	if (normalized.startsWith("06_canon/decisions/")) return "decision";
	return "note";
}

function noteIdFromPath(path: string): string {
	return normalizeVaultPath(path).replace(/\.md$/i, "");
}

function normalizeVaultPath(path: string): string {
	return path
		.replace(/\\/g, "/")
		.toLowerCase()
		.replace(/\s+/g, "_")
		.replace(/[^a-z0-9_./-]/g, "")
		.replace(/^_+|_+$/g, "");
}

function normalizeAliases(value: unknown): string[] {
	if (Array.isArray(value)) {
		return value.map((item) => String(item).trim()).filter(Boolean);
	}
	if (typeof value === "string" && value.trim()) {
		return [value.trim()];
	}
	return [];
}

function normalizeTags(tags: string[]): string[] {
	return tags.map((tag) => tag.trim()).filter(Boolean).sort();
}

function getVaultRootHint(app: App): string | null {
	try {
		// Desktop adapters expose getBasePath; mobile may not.
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		const basePath = (app.vault.adapter as any).getBasePath?.();
		return typeof basePath === "string" && basePath.trim() ? basePath : null;
	} catch {
		return null;
	}
}

function buildVaultId(app: App, vaultRootHint: string | null): string {
	const raw = `${app.vault.getName()}::${vaultRootHint ?? "unknown_root"}`;
	return createHash("sha256").update(raw).digest("hex").slice(0, 24);
}
