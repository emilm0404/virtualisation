#include <linux/init.h>
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/io.h>
#include <linux/platform_device.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Antigravity");
MODULE_DESCRIPTION("Hyper X GPU Zero-Copy VRAM DRM Platform Driver");
MODULE_VERSION("0.1");

#define DEVICE_NAME "hyperx_drm"
#define VRAM_GPA 0x40000000
#define VRAM_SIZE (256 * 1024 * 1024)
#define DOORBELL_GPA 0x3FFFF000
#define DOORBELL_SIZE 4096

static int major_number;
static void __iomem *vram_ptr;
static void __iomem *doorbell_ptr;

static int dev_open(struct inode *inodep, struct file *filep) {
    return 0;
}

static int dev_release(struct inode *inodep, struct file *filep) {
    return 0;
}

static ssize_t dev_write(struct file *filep, const char *buffer, size_t len, loff_t *offset) {
    uint32_t color = 0;
    if (len < sizeof(uint32_t)) {
        return -EINVAL;
    }
    if (copy_from_user(&color, buffer, sizeof(uint32_t))) {
        return -EFAULT;
    }

    iowrite32(color, vram_ptr);
    iowrite32(color, doorbell_ptr);

    pr_info("hyperx_drm: wrote color 0x%x to VRAM and rang doorbell.\n", color);
    return len;
}

static struct file_operations fops = {
    .open = dev_open,
    .release = dev_release,
    .write = dev_write,
};

static int __init hyperx_drm_init(void) {
    pr_info("hyperx_drm: initializing DRM platform driver.\n");

    major_number = register_chrdev(0, DEVICE_NAME, &fops);
    if (major_number < 0) {
        pr_err("hyperx_drm: failed to register major number.\n");
        return major_number;
    }

    vram_ptr = ioremap(VRAM_GPA, VRAM_SIZE);
    if (!vram_ptr) {
        pr_err("hyperx_drm: failed to map VRAM GPA.\n");
        unregister_chrdev(major_number, DEVICE_NAME);
        return -ENOMEM;
    }

    doorbell_ptr = ioremap(DOORBELL_GPA, DOORBELL_SIZE);
    if (!doorbell_ptr) {
        pr_err("hyperx_drm: failed to map Doorbell GPA.\n");
        iounmap(vram_ptr);
        unregister_chrdev(major_number, DEVICE_NAME);
        return -ENOMEM;
    }

    pr_info("hyperx_drm: char device registered. Major = %d. Map successful.\n", major_number);
    return 0;
}

static void __exit hyperx_drm_exit(void) {
    iounmap(doorbell_ptr);
    iounmap(vram_ptr);
    unregister_chrdev(major_number, DEVICE_NAME);
    pr_info("hyperx_drm: driver unloaded.\n");
}

module_init(hyperx_drm_init);
module_exit(hyperx_drm_exit);
