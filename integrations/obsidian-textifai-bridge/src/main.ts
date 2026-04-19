import {
	App,
	Notice,
	Plugin,
	PluginSettingTab,
	Setting,
	TAbstractFile,
	TFile,
	normalizePath,
} from "obsidian";

interface TextifAIBridgeSettings {
	exportPath: string;
	autoExportOnStartup: boolean;
	autoExportOnResolved: boolean;
	autoExportOnVaultChange: boolean;
	debounceMs: number;
	includeFullText: boolean;
}

const DEFAULT_SETTINGS: TextifAIBridgeSettings = {
	exportPath: ".textifai/obsidian-bridge-snapshot.json",
	autoExportOnStartup: true,
	autoExportOnResolved: true,
	autoExportOnVaultChange: true,
	debounceMs: 800,
	includeFullText: true,
};

export default class TextifAIBridgePlugin extends Plugin {
	settings: TextifAIBridgeSettings = DEFAULT_SETTINGS;
	private exportTimer: ReturnType<typeof setTimeout> | null = null;

	async onload(): Promise<void> {
		await this.loadSettings();
		this.addCommand({
			id: "export-textifai-context-snapshot",
			name: "Export TextifAI context snapshot",
			callback: async () => {
				await this.exportSnapshot("manual_command");
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
		if (this.exportTimer) {
			clearTimeout(this.exportTimer);
		}
		this.exportTimer = setTimeout(() => {
			void this.exportSnapshot(reason);
		}, this.settings.debounceMs);
	}

	private async exportSnapshot(reason: string): Promise<void> {
		const files = this.app.vault.getMarkdownFiles();
		const notes = [];
		const incomingByTarget: Record<string, Set<string>> = {};

		for (const file of files) {
			const cache = this.app.metadataCache.getFileCache(file);
			const body = this.settings.includeFullText ? await this.app.vault.cachedRead(file) : "";
			const resolved = this.app.metadataCache.resolvedLinks[file.path] ?? {};
			const unresolved = this.app.metadataCache.unresolvedLinks[file.path] ?? {};
			const outgoingLinks = Object.keys(resolved)
				.map((path) => path.replace(/\.md$/i, ""))
				.map((path) => path.replaceAll("\\", "/"));

			for (const targetPath of Object.keys(resolved)) {
				const normalizedTarget = targetPath.replace(/\.md$/i, "").replaceAll("\\", "/");
				incomingByTarget[normalizedTarget] ??= new Set<string>();
				incomingByTarget[normalizedTarget].add(file.path.replace(/\.md$/i, "").replaceAll("\\", "/"));
			}

			notes.push({
				note_id: linkPathId(file.path),
				title: file.basename,
				path: file.path,
				vault_relative_path: file.path,
				artifact_type: inferArtifactType(file.path),
				frontmatter: cache?.frontmatter ?? {},
				aliases: normalizeAliases(cache?.frontmatter?.aliases),
				project_confirmed_aliases: normalizeAliases(cache?.frontmatter?.project_confirmed_aliases),
				outgoing_links: outgoingLinks.map(linkPathId),
				incoming_links: [],
				raw_text: body,
				body_text: body,
				tags: (cache?.tags ?? []).map((tag) => tag.tag),
				headings: (cache?.headings ?? []).map((heading) => ({
					heading: heading.heading,
					level: heading.level,
				})),
				resolved_links: Object.fromEntries(
					Object.entries(resolved).map(([path, count]) => [linkPathId(path), count]),
				),
				unresolved_links: unresolved,
				source_kind: "obsidian_bridge_snapshot",
			});
		}

		for (const note of notes) {
			const incoming = incomingByTarget[note.vault_relative_path.replace(/\.md$/i, "")];
			note.incoming_links = incoming ? Array.from(incoming).map(linkPathId).sort() : [];
		}

		const payload = {
			schema_version: "1.0",
			source: "obsidian_textifai_bridge",
			generated_at: new Date().toISOString(),
			vault_name: this.app.vault.getName(),
			plugin_version: this.manifest.version,
			obsidian_app_version: (this.app as App & { version?: string }).version ?? null,
			export_reason: reason,
			notes,
		};

		const outputPath = normalizePath(this.settings.exportPath);
		const lastSlash = outputPath.lastIndexOf("/");
		if (lastSlash > 0) {
			const dir = outputPath.slice(0, lastSlash);
			try {
				// Hidden folders such as `.textifai` need adapter-level access.
				// mkdir is safe to retry; failures are ignored if the folder already exists.
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				await (this.app.vault.adapter as any).mkdir(dir);
			} catch {}
		}
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		await (this.app.vault.adapter as any).write(outputPath, JSON.stringify(payload, null, 2));
	}

	private async loadSettings(): Promise<void> {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
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
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.autoExportOnResolved).onChange(async (value) => {
					this.plugin.settings.autoExportOnResolved = value;
					await this.plugin.saveSettings();
				}),
			);

		new Setting(containerEl)
			.setName("Auto-export on vault changes")
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.autoExportOnVaultChange).onChange(async (value) => {
					this.plugin.settings.autoExportOnVaultChange = value;
					await this.plugin.saveSettings();
				}),
			);
	}
}

function inferArtifactType(path: string): string {
	const normalized = path.replaceAll("\\", "/");
	if (normalized.startsWith("03_Characters/Profiles/")) return "character";
	if (normalized.startsWith("02_World/Lore/")) return "lore";
	if (normalized.startsWith("04_Outline/Scenes/")) return "scene";
	if (normalized.startsWith("05_Draft/Chapters/")) return "chapter";
	if (normalized.startsWith("06_Canon/Decisions/")) return "decision";
	return "note";
}

function linkPathId(path: string): string {
	return path
		.replace(/\.md$/i, "")
		.replaceAll("\\", "/")
		.toLowerCase()
		.replace(/\s+/g, "_")
		.replace(/[^a-z0-9_/-]/g, "")
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
