/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Shared freestanding C core declarations for Open Connect.
 * Target builds use Linux 3.0 ARM EABI without target libc; host tests define
 * OC_HOST and compile the exact same translation units under ASan/UBSan.
 */
#ifndef OC_CORE_H
#define OC_CORE_H

typedef unsigned int oc_u32;
typedef unsigned long long oc_u64;
typedef unsigned char oc_u8;

typedef struct {
    oc_u32 state[8];
    oc_u64 bytes;
    unsigned used;
    oc_u8 block[64];
} OcHash;

enum { OC_READ=0, OC_WRITE=1, OC_RW=2, OC_DIRECTORY=4, OC_CREATE=8, OC_EXCLUSIVE=16, OC_BLOCKING=32, OC_TRUNC=64 };
enum { OC_REGULAR=0100000, OC_DIR=0040000, OC_TYPE=0170000 };
enum { OC_COPY_SOURCE=0, OC_COPY_OK=1, OC_COPY_DEST=-1 };

typedef struct {
    oc_u64 device, inode, size, modified, changed;
    oc_u32 mode, uid, gid, modified_ns, changed_ns;
} OcMeta;

enum { OC_PLAN_ROWS=192, OC_LINE_SIZE=1024, OC_PLAN_LIMIT=131072 };
typedef struct { char bytes[4096]; unsigned at, filled, total; int fd; } OcLines;
typedef struct { char *key, *path, *digest; OcMeta meta; int absent, used; } OcInput;

#define OC_DATA "tmp/mnt/data_persist/open-connect"
#define OC_RAM "tmp/open-connect"
enum { OC_SLOW=95, OC_STOCK=2, OC_REFUSE=1, OC_MEMBERS=128 };
enum { OC_GC_MAX=4 };

typedef struct { char *name, *digest; } OcMember;
typedef struct { OcMember rows[OC_MEMBERS]; unsigned count; } OcManifest;
typedef struct { const char *key, *path, *digest; int stock; } OcPin;

typedef struct {
    int root, data, ram, lock, snapshot, baseline, package, composed, stage, observer, log;
    char record[1024], next[1024], config[1024], access[320], selector[256], base_config[1024], base_access[320];
    char current_manifest[4096], base_manifest[4096], package_manifest[8192], composed_manifest[4096], composed_digest[65];
    char dependencies[24576], plan_text[OC_PLAN_LIMIT+1], scratch[32768];
    char *plugins; /* Reuse parsed dependency storage after coverage checks. */
    char *record_fields[13], *flags[9], *access_fields[6], *base_flags[9], *base_access_fields[6];
    OcManifest current, base, pkg, composition;
    OcInput inputs[OC_PLAN_ROWS];
    unsigned input_count;
    char boot[40], token[34], nonce[33], stage_name[64], observer_name[64], log_name[64], times[1024], svc_digest[65];
    unsigned time_count;
    long owner, group, parent;
    int selected, access_present, base_access_present, debited, input_failure;
    int gated, gate_sent, released, metadata_drift, touch_drift;
    unsigned ui_aliases; /* Low three bits: attempted; next three: linked. */
    OcMeta ui_identity[3];
} OcBoot;

typedef struct {
    char m_digest[12][65];
    OcMeta m_meta[12];
    char new_cfg[1024];
    char vui_list[4096];
    char seen_v[48][64];
} OcPub;

#ifdef OC_HOST
#include <fcntl.h>
#define OC_CWD AT_FDCWD
#else
#define OC_CWD (-100)
#endif

/* oc-hash.c */
void oc_hash_init(OcHash *h);
void oc_hash_add(OcHash *h, const void *input, unsigned size);
void oc_hash_finish(OcHash *h, char output[65]);

/* oc-io.c */
long oc_openat(int parent, const char *path, unsigned options, unsigned mode);
long oc_read(int fd, void *p, unsigned n);
long oc_write(int fd, const void *p, unsigned n);
long oc_close(int fd);
long oc_sync(int fd);
long oc_metadata(int fd, const char *path, OcMeta *m);
static inline long oc_stat(int fd, OcMeta *m) { return oc_metadata(fd, 0, m); }
long oc_parent(void);
long oc_worker_cpu1(void);
long oc_watch_parent(void);
long oc_owner(void);
long oc_group(void);
long oc_lock(int fd);
long oc_lock_sh(int fd);
long oc_unlock(int fd);
int oc_lock_held_ex(int fd);
int oc_is_wouldblock(long err);
void oc_sleep_ms(unsigned ms);
long oc_fork(void);
long oc_waitpid(int pid, int *status);
long oc_pipe(int fds[2]);
long oc_dup2(int oldfd, int newfd);
long oc_execve(const char *path, char *const argv[], char *const envp[]);
void oc_exit(int code);
long oc_set_cloexec(int fd, int on);
const char *oc_root_path(void);
int oc_nonroot_allowed(void);
long oc_mkdir(int fd, const char *name, unsigned mode);
long oc_unlink(int fd, const char *name);
long oc_rmdirat(int fd, const char *name);
long oc_rename(int fd, const char *from, const char *to);
long oc_link(int from, const char *name, int to, const char *target);
long oc_symlink(const char *source, int folder, const char *name);
long oc_readlink(int folder, const char *name, char *out, unsigned capacity);
long oc_mode(int fd, unsigned mode);
long oc_fchown(int fd, unsigned uid, unsigned gid);
void oc_u64_dec(oc_u64 v, char out[24]);
int oc_meta_mode_str(const OcMeta *m, char out[40]);
int oc_hash_file_at(int dir, const char *name, char digest[65], OcMeta *meta);
int oc_copy_file_at(int src_dir, const char *src_name, int dst_dir, const char *dst_name,
                    unsigned mode, int excl, int do_sync, char digest_out[65]);
int oc_run_cmd_io(const char *prog, char *const argv[], int in_fd, int out_fd, char *out, unsigned out_cap, int keep_fd);
static inline int oc_run_cmd(const char *prog, char *const argv[], int out_fd, char *out, unsigned out_cap, int keep_fd) {
    return oc_run_cmd_io(prog,argv,-1,out_fd,out,out_cap,keep_fd);
}
long oc_block(void);
#ifdef OC_HOST
void oc_cut(const char *phase);
#else
static inline void oc_cut(const char *phase) { (void)phase; }
#endif
int oc_stock_meta(int root, OcMeta *stock);
const char *oc_pin_digest(const char *key, const char *prod);
int oc_dir_iter(int folder, int (*cb)(const char *name, void *ctx), void *ctx);
long oc_beneath(int root, const char *path, unsigned options, unsigned mode);
int oc_meta_equal(const OcMeta *a, const OcMeta *b);
int oc_meta_resealable(const OcMeta *a, const OcMeta *b);
int oc_write_all(int fd, const void *input, unsigned n);
int oc_hash_copy(int input, int output, oc_u64 limit, char digest[65], OcMeta *metadata);
int oc_private(int fd);
int oc_open_private(int parent, const char *path);
int oc_absent_at(int root, const char *path);
int oc_text_fd(int fd, char *out, unsigned capacity);
int oc_text(int root, const char *path, char *out, unsigned capacity, int virtual_file);
int oc_verified_text(int folder, const char *name, const char *expected, char *out, unsigned capacity);
int oc_new_text(int folder, const char *name, const char *text, unsigned mode);
int oc_random(int root, char out[33]);

/* oc-manifest.c */
unsigned oc_length(const char *p);
int oc_equal(const char *a, const char *b);
int oc_prefix(const char *p, const char *prefix);
int oc_hex(const char *p, unsigned n);
int oc_key(const char *p);
int oc_one_line(char *p);
unsigned oc_fields(char *line, char **fields, unsigned capacity);
int oc_fields_line(char *text, char **fields, unsigned count);
int oc_join(char *out, unsigned capacity, const char *a, const char *b);
int oc_uuid(const char *p);
int oc_decimal(const char *p, oc_u64 *value);
void oc_put_hex(char *p, oc_u64 value, unsigned width);
oc_u64 oc_get_hex(const char *p, unsigned n);
char *oc_digest(OcManifest *manifest, const char *name);
int oc_manifest(char *text, OcManifest *manifest, int dependencies);
int oc_members(int folder, OcManifest *manifest, int expect_manifest);
int oc_load_manifest(int folder, const char *digest, char *text, unsigned capacity, OcManifest *manifest);
int oc_saved_text(int folder, OcManifest *manifest, const char *name, char *text, unsigned capacity);

/* oc-record.c */
int oc_record_parse_any(char *buf, char *fields[13]);
int oc_record_read_any(int data_fd, long owner, long group, char *buf, unsigned cap, char *fields[13]);
int oc_record_write_atomic(int root_fd, int data_fd, char *fields[13], char nonce_out[33]);
int oc_record_mode(OcBoot *b, const char *expected_before, const char *expected_after);
int oc_record(OcBoot *b);
int oc_record_file(OcBoot *b, const char *expected_before, const char *expected_after);
int oc_record_commit(OcBoot *b);

/* oc-config.c */
typedef struct {
    char *id, *label, *def, *enable, *disable;
} OcService;
typedef struct {
    OcService rows[16];
    unsigned count;
} OcCatalog;
typedef struct {
    int is_oc2;
    int has_autoshow;
    char *package, *touch, *warning, *nvram, *metadata, *base, *wireless, *autoshow, *pandora;
    char *svc_ids[16];
    char *svc_vals[16];
    unsigned svc_count;
} OcPrefs;
int oc_bit(const char *p);
int oc_nvram_value(const char *p);
int oc_metadata_mode(const char *text, unsigned *mode, unsigned *uid, unsigned *gid);
int oc_order(const char *a, const char *b);
int oc_service_id(const char *p);
int oc_service_keys(char *text, char **ids, unsigned *count);
int oc_catalog_load(char *text, unsigned bytes, OcCatalog *cat);
int oc_prefs_parse(char *text, const OcCatalog *cat, int active, OcPrefs *out);
int oc_prefs_write(const OcCatalog *cat, const OcPrefs *p, char *out, unsigned cap);
int oc_config(OcBoot *b, char *text, char **f, int active, char svc_digest[65]);
int oc_access(char *text, char **fields);
int oc_nvram_at(int root, char value[16]);
int oc_nvram(OcBoot *b, char value[16]);
int oc_lookup_vui_pin(const char *modules, const char *plugin, char out[65]);

/* oc-guard.c */
extern const char *const oc_root_names[19];
extern const char *const oc_root_paths[19];
extern const char *const oc_composed_names[12];
extern const OcPin oc_touch_pins[2];
extern const OcPin oc_base_pins[5];
int oc_mounts_mode(int root, char *scratch, unsigned cap, int allow_rw);
int oc_version_ok(int root, char *scratch, unsigned cap);
int oc_firmware_guard(int root, const char *op_tag, char *scratch, unsigned cap, const char **err_out);

/* oc-root.c */
int oc_remount(int root, const char *root_path, int rw);
int oc_nvram_change(int root, const char *expected, const char *desired);
int oc_root_publish(int root, const char *root_path, int data_fd, const char *rev,
                    const char *target_rel, const char *src_rel, const char *mode_str,
                    const char *expected_hash, const char *expected_mode,
                    const char *hold_rel, const char *hold_mode, int retire,
                    const char *base_snap, long owner, long group);
int oc_selector_matches_at(int root, const char *sel_hash, const char *sel_meta);
int oc_selector_pair_check(int root, int data_fd, const char *before_id, const char *after_id,
                           long owner, long group);
int oc_selector_apply(int root, const char *root_path, int data_fd, const char *rev,
                      const char *before_id, const char *after_id, const char *base_snap,
                      long owner, long group);
int oc_startup_staging_guard(int root);
int oc_startup_staging_retire(int root, const char *root_path, int data_fd, const char *rev,
                              const char *snap_id, const char *base_snap, long owner, long group);

/* oc-access.c */
int oc_access_key_verify(int data_fd, const char *key_id, long owner, long group);
int oc_access_key_import(int root, const char *root_path, int data_fd, long owner, long group,
                         char out_id[65], const char **err_out);
int oc_access_compose(int root, const char *root_path, int data_fd, const char *session_dir,
                      const char *base_snap, const char *console_dig, int work_fd,
                      const char *work_leaf, const char *uart, const char *ssh, const char *key,
                      long owner, long group);
int oc_access_hold_verify(int root, int data_fd, const char *base_snap, long owner, long group);
int oc_access_login_check(int root, int data_fd, const char *base_snap, long owner, long group);
int oc_access_hold_cleanup(int root, const char *root_path, int data_fd, const char *base_snap,
                           long owner, long group);
int oc_access_files_match(int root, int data_fd, const char *snap_id, long owner, long group);
int oc_access_targets_match(int root, int data_fd, const char *snap_id, const char *base_snap,
                            long owner, long group);
int oc_access_pair_check(int root, int data_fd, const char *before_id, const char *after_id,
                         const char *base_snap, long owner, long group);
int oc_access_pair_apply(int root, const char *root_path, int data_fd, const char *rev,
                         const char *before_id, const char *after_id, const char *base_snap,
                         int prepared_same_rev, long owner, long group);

/* oc-txn.c */
typedef struct {
    char mf_buf[4096];
    char cfg_buf[1024];
    char acc_buf[320];
    char sel_buf[256];
    OcManifest mf;
    char pkg[65], touch[4], warning[4], base[4], nvram[16], meta[40];
    char auto_dig[65], login_dig[65], ssh_dig[65];
    char *acc_f[6];
    char sel_hash[65], sel_meta[40], sel_pkg[65];
    int is_oc2, has_access, has_selector;
} OcTxnSnap;
extern OcTxnSnap oc_snap_pool[7];
extern char oc_mscratch[8192];
extern char oc_big_buf[32768];
int oc_txn_read_snap(int data_fd, const char *snap_id, OcTxnSnap *s);
int oc_pkg_boot_select(int data_fd, const char *root_path, const char *pkg_id,
                       long owner, long group, char bs_path[512]);
int oc_mounts_has(int root, const char *target, const char *fstype, int prefix_match);
void oc_rm_subdir(int parent, const char *leaf);
int oc_check_active_pins(int root, int data_fd, const char *pkg_id, const char *snap_id,
                         const char *base_val, const char *touch_val, const char **err_out);
int oc_targets_match(int root, int data_fd, const char *snap_id, const char *base_snap,
                     long owner, long group);
int oc_dependencies_match(int root, int data_fd, const char *snap_id, long owner, long group);
int oc_dependencies_pair_match(int root, int data_fd, const char *before_id, const char *after_id,
                               long owner, long group);
int oc_uninstall_owned(int data_fd, const char *snap_id, const char *base_snap, long owner, long group);
int oc_snapshot_create(int root, int data_fd, const char *autostart_snap, const char *pkg_id,
                       const char *nvram, const char *mode_str, const char *deps_snap,
                       int res_dir, const char *prefs_text, const char *session_dir,
                       const char *root_path, long owner, long group, char out_id[65]);
int oc_transaction_prepare(int root, int data_fd, char *rec[13], const char *phase,
                           const char *before_id, const char *after_id, const char *base_snap,
                           int skip_before_verify, long owner, long group, char nonce_out[33]);
int oc_transaction_reconcile(int root, const char *root_path, int data_fd, char *rec[13],
                             const char *session_dir, const char *prepared_rev,
                             long owner, long group, const char **err_out);
int oc_uninstall_cleanup(int root, const char *root_path, int data_fd, const char *session_dir,
                         long owner, long group, const char **err_out);

/* oc-api.c */
enum { OC_API_DONE=0, OC_API_ERR=1, OC_API_FALLBACK=2 };
int oc_join4(char *out, unsigned cap, const char *a, const char *b, const char *c, const char *d);
int oc_render_sm_profiles(int data_fd, const char *root_path, const char *pkg_id,
                          const char *snap_id, const char *cfg_path, unsigned cfg_len,
                          const char *warning_val, int out_dir);
int oc_api_handle(const char *token_path, const char *rev, const char *op,
                  const char *arg, const char *exp, const char *des);
int oc_api_cli(int argc, char **argv);
#ifdef OC_HOST
int oc_open_data_dir(int root);
int oc_open_ram_dir(int root);
int oc_data_absent(int root);
int oc_data_base(const char *root_path, char *out, unsigned cap);
#else
static inline int oc_open_data_dir(int root) { return oc_open_private(root,OC_DATA); }
static inline int oc_open_ram_dir(int root) { return oc_open_private(root,OC_RAM); }
static inline int oc_data_absent(int root) { return oc_absent_at(root,OC_DATA); }
static inline int oc_data_base(const char *root_path, char *out, unsigned cap) {
    return oc_join(out,cap,oc_equal(root_path,"/")?"":root_path,"/" OC_DATA);
}
#endif

/* oc-plan.c */
unsigned oc_meta_text(char *p, const OcMeta *m);
int oc_meta_parse(char **fields, OcMeta *m);
int oc_line(OcLines *r, char output[OC_LINE_SIZE]);
int oc_plan_rows(int root, int snapshot, int input, int output, int mode);
int oc_mounts(OcBoot *b);
int oc_input_mode(OcInput *input, const char *text);
OcInput *oc_find(OcBoot *b, const char *key);
OcInput *oc_expect(OcBoot *b, const char *key, const char *path, const char *digest);
int oc_plan(OcBoot *b);
int oc_expected_members(OcBoot *b, OcManifest *manifest, const char *key_prefix, const char *path_prefix);
int oc_dependency_coverage(OcBoot *b);
int oc_snapshot_coverage(OcBoot *b);
int oc_access_coverage(OcBoot *b);
int oc_identity_coverage(OcBoot *b);

/* oc-store.c */
int oc_audit_load(OcBoot *b, const char *root_path, const char *expected_current, const char *candidate, int allow_touch_drift);
int oc_audit(const char *root_path, const char *expected_current, const char *candidate);
int oc_seal_publish(const char *root_path, const char *expected_current, const char *work_rel, const char *expected_nvram);
int oc_gc_snapshots(const char *root_path, int lock_fd);

/* oc-boot.c */
extern OcBoot oc_boot;
void oc_stamp(OcBoot *b, const char *phase);
int oc_ui_stage(OcBoot *b);
int oc_policy_load(OcBoot *b);
int oc_load(OcBoot *b);
void oc_close_boot(OcBoot *b);
int oc_selection(int root, int gated);

#endif
