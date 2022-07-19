When using qemu64/kvm64/max(without `-accel kvm`):

```
# perf stat record --event=kvm:* -p 49399

 Performance counter stats for process id '49399':

                 0      kvm:kvm_entry                                               
                 0      kvm:kvm_hypercall                                           
                 0      kvm:kvm_hv_hypercall                                        
                 0      kvm:kvm_hv_hypercall_done                                   
                 0      kvm:kvm_xen_hypercall                                       
                 0      kvm:kvm_pio                                                 
                 0      kvm:kvm_fast_mmio                                           
                 0      kvm:kvm_cpuid                                               
                 0      kvm:kvm_apic                                                
                 0      kvm:kvm_exit                                                
                 0      kvm:kvm_inj_virq                                            
                 0      kvm:kvm_inj_exception                                       
                 0      kvm:kvm_page_fault                                          
                 0      kvm:kvm_msr                                                 
                 0      kvm:kvm_cr                                                  
                 0      kvm:kvm_pic_set_irq                                         
                 0      kvm:kvm_apic_ipi                                            
                 0      kvm:kvm_apic_accept_irq                                     
                 0      kvm:kvm_eoi                                                 
                 0      kvm:kvm_pv_eoi                                              
                 0      kvm:kvm_nested_vmrun                                        
                 0      kvm:kvm_nested_intercepts                                   
                 0      kvm:kvm_nested_vmexit                                       
                 0      kvm:kvm_nested_vmexit_inject                                   
                 0      kvm:kvm_nested_intr_vmexit                                   
                 0      kvm:kvm_invlpga                                             
                 0      kvm:kvm_skinit                                              
                 0      kvm:kvm_emulate_insn                                        
                 0      kvm:vcpu_match_mmio                                         
                 0      kvm:kvm_write_tsc_offset                                    
                 0      kvm:kvm_update_master_clock                                   
                 0      kvm:kvm_track_tsc                                           
                 0      kvm:kvm_pml_full                                            
                 0      kvm:kvm_ple_window_update                                   
                 0      kvm:kvm_pvclock_update                                      
                 0      kvm:kvm_wait_lapic_expire                                   
                 0      kvm:kvm_smm_transition                                      
                 0      kvm:kvm_pi_irte_update                                      
                 0      kvm:kvm_hv_notify_acked_sint                                   
                 0      kvm:kvm_hv_synic_set_irq                                    
                 0      kvm:kvm_hv_synic_send_eoi                                   
                 0      kvm:kvm_hv_synic_set_msr                                    
                 0      kvm:kvm_hv_stimer_set_config                                   
                 0      kvm:kvm_hv_stimer_set_count                                   
                 0      kvm:kvm_hv_stimer_start_periodic                                   
                 0      kvm:kvm_hv_stimer_start_one_shot                                   
                 0      kvm:kvm_hv_stimer_callback                                   
                 0      kvm:kvm_hv_stimer_expiration                                   
                 0      kvm:kvm_hv_stimer_cleanup                                   
                 0      kvm:kvm_apicv_update_request                                   
                 0      kvm:kvm_avic_incomplete_ipi                                   
                 0      kvm:kvm_avic_unaccelerated_access                                   
                 0      kvm:kvm_avic_ga_log                                         
                 0      kvm:kvm_hv_timer_state                                      
                 0      kvm:kvm_hv_flush_tlb                                        
                 0      kvm:kvm_hv_flush_tlb_ex                                     
                 0      kvm:kvm_hv_send_ipi                                         
                 0      kvm:kvm_hv_send_ipi_ex                                      
                 0      kvm:kvm_pv_tlb_flush                                        
                 0      kvm:kvm_nested_vmenter_failed                                   
                 0      kvm:kvm_hv_syndbg_set_msr                                   
                 0      kvm:kvm_hv_syndbg_get_msr                                   
                 0      kvm:kvm_vmgexit_enter                                       
                 0      kvm:kvm_vmgexit_exit                                        
                 0      kvm:kvm_vmgexit_msr_protocol_enter                                   
                 0      kvm:kvm_vmgexit_msr_protocol_exit                                   
                 0      kvm:kvm_userspace_exit                                      
                 0      kvm:kvm_vcpu_wakeup                                         
                 0      kvm:kvm_set_irq                                             
                 0      kvm:kvm_ioapic_set_irq                                      
                 0      kvm:kvm_ioapic_delayed_eoi_inj                                   
                 0      kvm:kvm_msi_set_irq                                         
                 0      kvm:kvm_ack_irq                                             
                 0      kvm:kvm_mmio                                                
                 0      kvm:kvm_fpu                                                 
                 0      kvm:kvm_try_async_get_page                                   
                 0      kvm:kvm_async_pf_doublefault                                   
                 0      kvm:kvm_async_pf_not_present                                   
                 0      kvm:kvm_async_pf_ready                                      
                 0      kvm:kvm_async_pf_completed                                   
                 0      kvm:kvm_halt_poll_ns                                        
                 0      kvm:kvm_dirty_ring_push                                     
                 0      kvm:kvm_dirty_ring_reset                                    
                 0      kvm:kvm_dirty_ring_exit                                     
                 0      kvm:kvm_unmap_hva_range                                     
                 0      kvm:kvm_set_spte_hva                                        
                 0      kvm:kvm_age_hva                                             
                 0      kvm:kvm_test_age_hva                                        

      10.010339406 seconds time elapsed
      
# perf stat record -p 76890

 Performance counter stats for process id '76890':

         12,380.16 msec task-clock                #    1.031 CPUs utilized          
            43,097      context-switches          #    3.481 K/sec                  
               183      cpu-migrations            #   14.782 /sec                   
                74      page-faults               #    5.977 /sec                   
    47,946,065,155      cycles                    #    3.873 GHz                    
   146,386,239,331      instructions              #    3.05  insn per cycle         
    21,486,578,571      branches                  #    1.736 G/sec                  
        77,108,017      branch-misses             #    0.36% of all branches        

      12.009781217 seconds time elapsed
```

[my CPU: i5-8279U](https://www.intel.co.uk/content/www/uk/en/products/sku/191070/intel-core-i58279u-processor-6m-cache-up-to-4-10-ghz/specifications.html)

with `-accel kvm` or `-enable-kvm`, zCore cannot boot correctly