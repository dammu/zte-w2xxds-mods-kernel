#!/usr/bin/env python3
"""Insert BakaSU (kafuuchino mix4-5.4 branch) manual hooks into the ZTE 5.4.276 tree.
Every anchor must match exactly once; otherwise the script aborts without writing."""
import sys, re
root = sys.argv[1] if len(sys.argv) > 1 else '.'
def edit(rel, fn):
    p = f'{root}/{rel}'; s = open(p).read(); n = fn(s); assert n != s, rel; open(p, 'w').write(n); print('patched', rel)
def rep1(s, old, new):
    assert s.count(old) == 1, ('anchor count', s.count(old), old[:60]); return s.replace(old, new, 1)

def exec_c(s):
    s = rep1(s, 'static int __do_execve_file(int fd, struct filename *filename,',
'''#ifdef CONFIG_KSU_MANUAL_HOOK
extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,
			       void *argv, void *envp, int *flags);
extern int ksu_handle_post_execveat(int *fd, struct filename **filename_ptr,
				    void *argv, void *envp, int *flags,
				    int *retval);
#endif

static int __do_execve_file(int fd, struct filename *filename,''')
    s = rep1(s, '''	int retval;

	if (IS_ERR(filename))
		return PTR_ERR(filename);
''', '''	int retval;

#ifdef CONFIG_KSU_MANUAL_HOOK
	if (!IS_ERR_OR_NULL(filename))
		ksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);
#endif
	if (IS_ERR(filename))
		return PTR_ERR(filename);
''')
    s = rep1(s, '''out_ret:
	if (filename)
		putname(filename);
	return retval;
''', '''out_ret:
#ifdef CONFIG_KSU_MANUAL_HOOK
	if (filename)
		ksu_handle_post_execveat(&fd, &filename, &argv, &envp, &flags,
					 &retval);
#endif
	if (filename)
		putname(filename);
	return retval;
''')
    return s

def open_c(s):
    return rep1(s, '''SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)
{
	return do_faccessat(dfd, filename, mode);
}''', '''#ifdef CONFIG_KSU_MANUAL_HOOK
extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,
				int *mode, int *flags);
#endif

SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)
{
#ifdef CONFIG_KSU_MANUAL_HOOK
	ksu_handle_faccessat(&dfd, &filename, &mode, NULL);
#endif
	return do_faccessat(dfd, filename, mode);
}''')

def stat_c(s):
    s = rep1(s, '#include <asm/unistd.h>\n', '''#include <asm/unistd.h>

#ifdef CONFIG_KSU_MANUAL_HOOK
extern int ksu_handle_stat(int *dfd, const char __user **filename_user,
			   int *flags);
extern void ksu_handle_vfs_fstat(int fd, loff_t *kstat_size_ptr);
#endif
''')
    # vfs_statx_fd: hook after vfs_getattr succeeded, before fdput
    m = re.search(r'int vfs_statx_fd\(.*?\n}\n', s, re.S); assert m, 'vfs_statx_fd'
    body = m.group(0); assert body.count('\t\tfdput(f);\n') == 1, body
    nb = body.replace('\t\tfdput(f);\n', '''#ifdef CONFIG_KSU_MANUAL_HOOK
		if (!error)
			ksu_handle_vfs_fstat(fd, &stat->size);
#endif
		fdput(f);
''', 1)
    s = s.replace(body, nb, 1)
    s = rep1(s, '''SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,
		struct stat __user *, statbuf, int, flag)
{
	struct kstat stat;
	int error;

	error = vfs_fstatat(dfd, filename, &stat, flag);''', '''SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,
		struct stat __user *, statbuf, int, flag)
{
	struct kstat stat;
	int error;

#ifdef CONFIG_KSU_MANUAL_HOOK
	ksu_handle_stat(&dfd, &filename, &flag);
#endif
	error = vfs_fstatat(dfd, filename, &stat, flag);''')
    s = rep1(s, '''SYSCALL_DEFINE4(fstatat64, int, dfd, const char __user *, filename,
		struct stat64 __user *, statbuf, int, flag)
{
	struct kstat stat;
	int error;

	error = vfs_fstatat(dfd, filename, &stat, flag);''', '''SYSCALL_DEFINE4(fstatat64, int, dfd, const char __user *, filename,
		struct stat64 __user *, statbuf, int, flag)
{
	struct kstat stat;
	int error;

#ifdef CONFIG_KSU_MANUAL_HOOK /* 32-bit su */
	ksu_handle_stat(&dfd, &filename, &flag);
#endif
	error = vfs_fstatat(dfd, filename, &stat, flag);''')
    return s

def reboot_c(s):
    return rep1(s, '''SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,
		void __user *, arg)
{
	struct pid_namespace *pid_ns = task_active_pid_ns(current);
	char buffer[256];
	int ret = 0;

	/* We only trust the superuser with rebooting the system. */''', '''#ifdef CONFIG_KSU_MANUAL_HOOK
extern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd,
				 void __user **arg);
#endif

SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,
		void __user *, arg)
{
	struct pid_namespace *pid_ns = task_active_pid_ns(current);
	char buffer[256];
	int ret = 0;

#ifdef CONFIG_KSU_MANUAL_HOOK
	ksu_handle_sys_reboot(magic1, magic2, cmd, &arg);
#endif
	/* We only trust the superuser with rebooting the system. */''')

edit('fs/exec.c', exec_c); edit('fs/open.c', open_c); edit('fs/stat.c', stat_c); edit('kernel/reboot.c', reboot_c)
print('all hooks applied')
